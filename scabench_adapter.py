from __future__ import annotations

from typing import Any


def _summary_total(summary: dict[str, Any]) -> int:
    total = 0
    for key in ("passed", "failed", "skipped", "timed_out"):
        value = summary.get(key)
        if isinstance(value, int) and value > 0:
            total += value
    if total <= 0:
        total = int(summary.get("total", 0) or summary.get("cases", 0) or 1)
    return max(total, 1)


def _confidence_bonus(entry: dict[str, Any]) -> float:
    ladder = entry.get("confidence_ladder")
    if not isinstance(ladder, dict):
        return 0.0
    weights = {"high": 1.0, "partial": 0.45, "not_yet": 0.0}
    keys = ("methodology", "environment", "detection", "reproduction", "comparative_data")
    values = [weights.get(str(ladder.get(key, "")).lower(), 0.0) for key in keys]
    return sum(values) / len(keys) if values else 0.0


def adapt(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not entry:
        return {
            "adapter": "scabench",
            "score": 0,
            "grade": "unscored",
            "total_cases": 0,
            "signal_ratio": 0.0,
            "reproduction_ratio": 0.0,
            "stability_ratio": 0.0,
            "summary": "No benchmark run is available yet.",
        }

    summary = entry.get("results_summary") if isinstance(entry.get("results_summary"), dict) else {}
    total = _summary_total(summary)
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    skipped = int(summary.get("skipped", 0) or 0)
    timed_out = int(summary.get("timed_out", 0) or 0)
    aligned = int(summary.get("aligned", 0) or 0)
    signals = int(summary.get("detector_signals", 0) or 0)
    investigate = int(summary.get("investigate", 0) or 0)
    diverged = int(summary.get("diverged", 0) or 0)
    environment_sensitive = int(summary.get("environment_sensitive", 0) or 0)

    reproduction_ratio = passed / total
    signal_ratio = min(signals / total, 1.0)
    stability_ratio = max(0.0, 1.0 - ((failed + timed_out + diverged) / total))
    alignment_ratio = aligned / total
    coverage_ratio = max(0.0, 1.0 - (skipped / total))
    confidence_ratio = _confidence_bonus(entry)

    score = round(
        100.0
        * (
            0.34 * reproduction_ratio
            + 0.20 * signal_ratio
            + 0.18 * stability_ratio
            + 0.14 * alignment_ratio
            + 0.07 * coverage_ratio
            + 0.07 * confidence_ratio
        )
    )
    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "E"

    return {
        "adapter": "scabench",
        "score": score,
        "grade": grade,
        "total_cases": total,
        "reproduction_ratio": round(reproduction_ratio, 3),
        "signal_ratio": round(signal_ratio, 3),
        "stability_ratio": round(stability_ratio, 3),
        "alignment_ratio": round(alignment_ratio, 3),
        "coverage_ratio": round(coverage_ratio, 3),
        "confidence_ratio": round(confidence_ratio, 3),
        "summary": (
            f"ScaBench score {score}/100 from reproduction, detector signals, stability, and confidence. "
            f"Issues: failed={failed}, timed_out={timed_out}, skipped={skipped}, investigate={investigate}, diverged={diverged}, env_sensitive={environment_sensitive}."
        ),
    }
