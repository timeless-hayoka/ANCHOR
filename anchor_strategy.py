"""Evidence-driven hunt prioritization for ANCHOR.

Consumes canonical trend output and the outcome ledger — never recomputes trends.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from anchor_trends import compute_benchmark_trends, format_challenge_label

IMPACT_BY_STATUS = {
    "FAILED": 0.85,
    "TIMED_OUT": 1.0,
    "SKIPPED": 0.35,
    "PASSED": 0.0,
}

EFFORT_SCORE = {"low": 1.0, "medium": 2.0, "high": 4.0}

PATTERN_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Repeated timeout", re.compile(r"timeout|timed out|time.?out|brute.?force|create2", re.I)),
    ("Detector mismatch", re.compile(r"detector|slither|mythril|signal|finding", re.I)),
    ("Environment issue", re.compile(r"environment|rpc|fork|network|sensitive", re.I)),
    ("False detector signal", re.compile(r"false positive|noise|benign|info.?only", re.I)),
]

PATTERN_RECOMMENDATIONS = {
    "Repeated timeout": "Increase per-challenge timeout or add deterministic search cache.",
    "Detector mismatch": "Tighten target relevance filters before reproduction attempts.",
    "Environment issue": "Document RPC/fork prerequisites and add negative controls.",
    "False detector signal": "Down-rank info-only detector hits in the hunt queue.",
}


def categorize_lesson(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "Uncategorized"
    for label, pattern in PATTERN_RULES:
        if pattern.search(cleaned):
            return label
    return "Other"


def summarize_outcome_patterns(outcome_entries: list[dict], limit: int = 50) -> dict[str, Any]:
    rows = sorted(outcome_entries, key=lambda entry: entry.get("timestamp", ""), reverse=True)[:limit]
    pattern_counts: dict[str, int] = {}
    for entry in rows:
        lesson = (entry.get("lesson") or entry.get("note") or "").strip()
        if not lesson:
            continue
        category = categorize_lesson(lesson)
        pattern_counts[category] = pattern_counts.get(category, 0) + 1

    top_pattern = max(pattern_counts.items(), key=lambda item: item[1])[0] if pattern_counts else None
    return {
        "pattern_counts": pattern_counts,
        "top_pattern": top_pattern,
        "recommendation": PATTERN_RECOMMENDATIONS.get(top_pattern or "", ""),
    }


def estimate_effort(profile: dict[str, Any]) -> tuple[str, float]:
    if profile.get("requires_rpc"):
        return "high", EFFORT_SCORE["high"]
    if profile.get("timeout_count", 0) >= 2 or profile.get("last_status") == "TIMED_OUT":
        return "medium", EFFORT_SCORE["medium"]
    if profile.get("comparison") == "environment_sensitive":
        return "medium", EFFORT_SCORE["medium"]
    return "low", EFFORT_SCORE["low"]


def estimate_impact(profile: dict[str, Any]) -> float:
    status = str(profile.get("last_status", "")).upper()
    base = IMPACT_BY_STATUS.get(status, 0.5)
    if profile.get("instability_score", 0) >= 3:
        base = min(1.0, base + 0.1)
    return base


def estimate_confidence(profile: dict[str, Any], outcome_patterns: dict[str, Any]) -> tuple[str, float]:
    recurrence = min(1.0, (profile.get("timeout_count", 0) + profile.get("status_changes", 0)) / 3.0)
    if profile.get("last_status") == "TIMED_OUT" and recurrence >= 0.5:
        return "high", 0.9
    if profile.get("last_status") == "FAILED" and profile.get("stability_ratio", 0) < 0.5:
        return "medium", 0.65
    if outcome_patterns.get("top_pattern") == "Repeated timeout" and profile.get("timeout_count", 0) >= 1:
        return "high", 0.85
    if recurrence >= 0.33:
        return "medium", 0.6
    return "low", 0.4


def build_reason(profile: dict[str, Any], outcome_patterns: dict[str, Any]) -> str:
    if profile.get("timeout_count", 0) >= 2:
        return "Repeated timeout across multiple published runs."
    if profile.get("last_status") == "TIMED_OUT":
        return "Latest run timed out before reproduction completed."
    if profile.get("comparison") == "environment_sensitive":
        return "Results vary with environment; needs controlled reproduction."
    if profile.get("last_status") == "FAILED":
        return "Consistent failure — high leverage if root cause is found."
    top = outcome_patterns.get("top_pattern")
    if top and top != "Other":
        return f"Outcome ledger highlights pattern: {top}."
    return "Open benchmark challenge with measurable instability."


def expected_gain(profile: dict[str, Any], latest_level: str) -> str:
    label = profile.get("label") or format_challenge_label(profile.get("challenge", "challenge"))
    level = latest_level or "Phase 1"
    return f"Resolving {label} advances DVD {level} benchmark completion."


def roi_stars(score: float) -> str:
    filled = max(1, min(5, int(round(score * 5))))
    return "⭐" * filled


def rank_hunt_candidates(
    trends: dict[str, Any],
    outcome_patterns: dict[str, Any],
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = trends.get("challenge_profiles") or {}
    latest_level = ""
    runs = trends.get("runs") or []
    if runs:
        latest_level = str(runs[-1].get("level") or "Phase 1")

    candidates: list[dict[str, Any]] = []
    for challenge, profile in profiles.items():
        if str(profile.get("last_status", "")).upper() == "PASSED":
            candidates.append(
                {
                    "challenge": challenge,
                    "label": profile.get("label", format_challenge_label(challenge)),
                    "status": "complete",
                    "impact": "solved",
                    "effort": "low",
                    "confidence": "high",
                    "roi": 0.0,
                    "roi_stars": "Complete",
                    "reason": "Already passing in latest published run.",
                    "expected_gain": "No action required.",
                }
            )
            continue

        impact_val = estimate_impact(profile)
        effort_label, effort_val = estimate_effort(profile)
        confidence_label, confidence_val = estimate_confidence(profile, outcome_patterns)
        recurrence = min(1.0, (profile.get("timeout_count", 0) + profile.get("status_changes", 0)) / 3.0)
        roi = (impact_val * confidence_val * max(recurrence, 0.25)) / effort_val

        candidates.append(
            {
                "challenge": challenge,
                "label": profile.get("label", format_challenge_label(challenge)),
                "status": "open",
                "impact": "high" if impact_val >= 0.85 else "medium",
                "effort": effort_label,
                "confidence": confidence_label,
                "roi": round(roi, 4),
                "roi_stars": roi_stars(roi),
                "reason": build_reason(profile, outcome_patterns),
                "expected_gain": expected_gain(profile, latest_level),
                "last_status": profile.get("last_status"),
                "timeout_count": profile.get("timeout_count", 0),
            }
        )

    open_candidates = [row for row in candidates if row.get("status") == "open"]
    open_candidates.sort(key=lambda row: row.get("roi", 0), reverse=True)
    complete = [row for row in candidates if row.get("status") == "complete"]
    return (open_candidates[:top_n] + complete[: max(0, top_n - len(open_candidates[:top_n]))])[:top_n]


def compute_strategy(
    benchmark_entries: list[dict],
    outcome_entries: list[dict],
    *,
    root,
    trends_limit: int = 10,
    outcome_limit: int = 50,
    top_n: int = 5,
    trends_loader: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    loader = trends_loader or compute_benchmark_trends
    trends = loader(benchmark_entries, root=root, limit=trends_limit)
    outcome_patterns = summarize_outcome_patterns(outcome_entries, limit=outcome_limit)
    ranked = rank_hunt_candidates(trends, outcome_patterns, top_n=top_n)
    recommendation = ranked[0] if ranked and ranked[0].get("status") == "open" else None

    return {
        "schema_version": "1.0",
        "source": "anchor_strategy.compute_strategy",
        "trends_schema": trends.get("schema_version"),
        "outcome_patterns": outcome_patterns,
        "recommendations": ranked,
        "next_hunt": recommendation,
        "trends_ref": {
            "published_count": trends.get("published_count"),
            "average_reproduction_rate": trends.get("average_reproduction_rate"),
            "most_unstable_challenge": trends.get("most_unstable_challenge"),
        },
    }


def render_strategy(payload: dict[str, Any]) -> str:
    recommendation = payload.get("next_hunt")
    if not recommendation:
        return "No open hunt recommendations — all tracked challenges passing or insufficient published history."

    lines = [
        "Next Recommended Hunt",
        "",
        recommendation.get("label", recommendation.get("challenge", "—")),
        "",
        "Reason",
        "",
        recommendation.get("reason", "—"),
        "",
        "Expected Gain",
        "",
        recommendation.get("expected_gain", "—"),
        "",
        "Confidence",
        "",
        str(recommendation.get("confidence", "—")).title(),
        "",
        "Estimated Effort",
        "",
        str(recommendation.get("effort", "—")).title(),
        "",
        f"ROI: {recommendation.get('roi_stars', '—')} ({recommendation.get('roi', '—')})",
        "",
    ]

    patterns = payload.get("outcome_patterns") or {}
    counts = patterns.get("pattern_counts") or {}
    if counts:
        lines.extend(["Lessons Learned (grouped)", ""])
        for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"{label}: {count}")
        lines.append("")
        if patterns.get("top_pattern"):
            lines.extend(
                [
                    "Common Failure Pattern",
                    "",
                    patterns["top_pattern"],
                    "",
                ]
            )
        if patterns.get("recommendation"):
            lines.extend(
                [
                    "Recommendation",
                    "",
                    patterns["recommendation"],
                    "",
                ]
            )

    others = [row for row in (payload.get("recommendations") or []) if row.get("status") == "open"][1:4]
    if others:
        lines.extend(["Also consider", ""])
        for row in others:
            lines.append(f"- {row.get('label')}: {row.get('roi_stars')} — {row.get('reason')}")
        lines.append("")

    lines.append("Canonical source: anchor_strategy.compute_strategy (consumes anchor_trends, not duplicate math).")
    return "\n".join(lines)
