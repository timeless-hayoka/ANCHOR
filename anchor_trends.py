"""Canonical benchmark trend engine for ANCHOR.

Single source for historical comparison. Consumed by:
- ``anchor benchmark trends`` (CLI)
- ``/api/anchor/benchmark/trends`` (HTTP)
- future strategy engine and dashboard panels

Do not duplicate trend math elsewhere — import from this module.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from statistics import mean
from typing import Any, Callable

STATUS_SCORES = {
    "PASSED": 3,
    "SKIPPED": 2,
    "TIMED_OUT": 1,
    "FAILED": 0,
}


def parse_iso_timestamp(value: str) -> dt.datetime | None:
    if not value or value in {"unknown", ""}:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def is_published(entry: dict) -> bool:
    return entry.get("publication_tier", "development") == "published"


def status_score(value: str) -> int:
    return STATUS_SCORES.get(str(value).upper(), -1)


def load_benchmark_artifact(entry: dict, root: Path) -> dict:
    candidates: list[Path] = []
    for key in ("artifact_json", "record"):
        value = entry.get(key)
        if value:
            candidates.append(root / value)
    for key in ("artifact_json", "record"):
        value = entry.get(key)
        if not value:
            continue
        candidate = root / value
        if candidate.name in {"README.md", "benchmark.json", "storage.json", "PUBLISHED.md"}:
            candidates.append(candidate.parent / "benchmark.json")
    for candidate in candidates:
        bench = candidate if candidate.name == "benchmark.json" else candidate.parent / "benchmark.json"
        for path in (candidate, bench):
            if path.exists() and path.suffix == ".json":
                try:
                    payload = path.read_text(encoding="utf-8")
                    import json

                    data = json.loads(payload)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
    return {"results": [], "summary": entry.get("results_summary", {}) or {}}


def benchmark_result_index(entry: dict, root: Path) -> dict[str, dict]:
    payload = load_benchmark_artifact(entry, root)
    index: dict[str, dict] = {}
    for result in payload.get("results", []) or []:
        challenge = result.get("challenge")
        if challenge:
            index[str(challenge)] = result
    return index


def summary_for_entry(entry: dict, root: Path) -> dict:
    summary = entry.get("results_summary")
    if isinstance(summary, dict) and summary:
        return summary
    artifact_summary = load_benchmark_artifact(entry, root).get("summary", {})
    return artifact_summary if isinstance(artifact_summary, dict) else {}


def reproduction_rate(summary: dict) -> float | None:
    passed = int(summary.get("passed") or 0)
    failed = int(summary.get("failed") or 0)
    timed_out = int(summary.get("timed_out") or 0)
    skipped = int(summary.get("skipped") or 0)
    total = passed + failed + timed_out + skipped
    if total <= 0:
        return None
    return passed / total


def format_challenge_label(challenge: str) -> str:
    return challenge.replace("-", " ").replace("_", " ").title()


def chronological_published(entries: list[dict], limit: int = 10) -> list[dict]:
    published = [entry for entry in entries if is_published(entry)]
    published.sort(
        key=lambda entry: parse_iso_timestamp(str(entry.get("executed_at", "")))
        or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    )
    if limit > 0 and len(published) > limit:
        return published[-limit:]
    return published


def compute_benchmark_trends(
    entries: list[dict],
    *,
    root: Path,
    limit: int = 10,
    artifact_loader: Callable[[dict], dict] | None = None,
) -> dict[str, Any]:
    """Build structured trend payload from manifest benchmark entries."""

    def _artifact(entry: dict) -> dict:
        if artifact_loader is not None:
            return artifact_loader(entry)
        return load_benchmark_artifact(entry, root)

    runs_chron = chronological_published(entries, limit)
    run_rows: list[dict[str, Any]] = []
    rates: list[float] = []

    for entry in runs_chron:
        summary = summary_for_entry(entry, root)
        rate = reproduction_rate(summary)
        run_rows.append(
            {
                "run_id": entry.get("id", ""),
                "target": entry.get("target", ""),
                "level": entry.get("level", ""),
                "executed_at": entry.get("executed_at", ""),
                "reproduction_rate": rate,
                "passed": summary.get("passed"),
                "failed": summary.get("failed"),
                "timed_out": summary.get("timed_out"),
            }
        )
        if rate is not None:
            rates.append(rate)

    avg_rate = mean(rates) if rates else None
    trend_delta: float | None = None
    trend_direction = "flat"
    if len(rates) >= 2:
        trend_delta = rates[-1] - rates[0]
        if trend_delta > 0.005:
            trend_direction = "up"
        elif trend_delta < -0.005:
            trend_direction = "down"

    challenge_timelines: dict[str, list[dict[str, Any]]] = {}
    for entry in runs_chron:
        run_id = str(entry.get("id", ""))
        for challenge, result in benchmark_result_index(entry, root).items():
            status = str(result.get("status", result.get("reproduction_status", "unknown"))).upper()
            challenge_timelines.setdefault(challenge, []).append(
                {
                    "run_id": run_id,
                    "status": status,
                    "score": status_score(status),
                    "timed_out": bool(result.get("timed_out")),
                }
            )

    best_improvement = -999
    top_improved: dict[str, Any] | None = None
    worst_instability = -1
    most_unstable: dict[str, Any] | None = None

    for challenge, timeline in challenge_timelines.items():
        if len(timeline) < 2:
            continue
        first_score = timeline[0]["score"]
        last_score = timeline[-1]["score"]
        if first_score >= 0 and last_score >= 0:
            improvement = last_score - first_score
            if improvement > best_improvement:
                best_improvement = improvement
                top_improved = {
                    "challenge": challenge,
                    "label": format_challenge_label(challenge),
                    "first_status": timeline[0]["status"],
                    "last_status": timeline[-1]["status"],
                    "score_delta": improvement,
                }

        status_changes = sum(
            1 for idx in range(1, len(timeline)) if timeline[idx]["status"] != timeline[idx - 1]["status"]
        )
        timeout_count = sum(1 for row in timeline if row["timed_out"] or row["status"] == "TIMED_OUT")
        instability = status_changes * 2 + timeout_count
        if instability > worst_instability:
            worst_instability = instability
            most_unstable = {
                "challenge": challenge,
                "label": format_challenge_label(challenge),
                "status_changes": status_changes,
                "timeout_count": timeout_count,
                "instability_score": instability,
            }

    return {
        "schema_version": "1.0",
        "published_count": len(runs_chron),
        "limit": limit,
        "runs": run_rows,
        "average_reproduction_rate": avg_rate,
        "trend_delta": trend_delta,
        "trend_direction": trend_direction,
        "top_improved_challenge": top_improved,
        "most_unstable_challenge": most_unstable,
    }


def format_percent(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.0f}%"


def format_trend_arrow(trend_delta: float | None) -> str:
    if trend_delta is None:
        return "→ n/a"
    pct = trend_delta * 100
    if pct > 0.5:
        return f"▲ +{pct:.0f}%"
    if pct < -0.5:
        return f"▼ {pct:.0f}%"
    return "→ flat"


def render_benchmark_trends(trends: dict[str, Any]) -> str:
    if not trends.get("published_count"):
        return "No published benchmark runs available yet."

    count = trends["published_count"]
    limit = trends.get("limit", count)
    lines = [
        f"Last {count} Published Run{'s' if count != 1 else ''}" + (f" (limit {limit})" if limit and count >= limit else ""),
        "",
    ]

    for row in trends.get("runs", []):
        lines.append(
            f"- {row.get('run_id', 'unknown')}: "
            f"{format_percent(row.get('reproduction_rate'))} "
            f"(pass={row.get('passed', '—')} fail={row.get('failed', '—')} t/o={row.get('timed_out', '—')})"
        )

    lines.extend(
        [
            "",
            "Average Reproduction Rate",
            "",
            format_percent(trends.get("average_reproduction_rate")),
            "",
            "Trend",
            "",
            format_trend_arrow(trends.get("trend_delta")),
            "",
        ]
    )

    improved = trends.get("top_improved_challenge")
    if improved:
        lines.extend(
            [
                "Top Improved Challenge",
                "",
                improved.get("label", improved.get("challenge", "—")),
                "",
            ]
        )
    else:
        lines.extend(["Top Improved Challenge", "", "—", ""])

    unstable = trends.get("most_unstable_challenge")
    if unstable:
        lines.extend(
            [
                "Most Unstable",
                "",
                unstable.get("label", unstable.get("challenge", "—")),
                "",
            ]
        )
    else:
        lines.extend(["Most Unstable", "", "—", ""])

    lines.append("Canonical source: anchor_trends.compute_benchmark_trends — use for dashboard and strategy.")
    return "\n".join(lines)
