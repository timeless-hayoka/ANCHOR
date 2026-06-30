"""Collect and normalize evidence artifacts for outcome insights."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anchor_trends import load_benchmark_artifact, parse_iso_timestamp, reproduction_rate, summary_for_entry

EVIDENCE_SCHEMA_VERSION = "1.0"
EVIDENCE_KINDS = ("benchmark", "bugbot_training", "hunt_analysis")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _rel_path(path: Path, anchor_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(anchor_root.resolve()))
    except ValueError:
        return str(path)


def _timestamp_sort_key(value: str) -> float:
    parsed = parse_iso_timestamp(value)
    if parsed is None:
        return float("-inf")
    return parsed.timestamp()


def normalize_benchmark_evidence(
    *,
    manifest_entry: dict[str, Any],
    anchor_root: Path,
) -> dict[str, Any] | None:
    artifact_path = manifest_entry.get("artifact_json") or manifest_entry.get("record")
    if not artifact_path:
        return None
    path = anchor_root / str(artifact_path)
    payload = load_benchmark_artifact(manifest_entry, anchor_root)
    summary = summary_for_entry(manifest_entry, anchor_root)
    if not isinstance(summary, dict):
        summary = payload.get("results_summary") or payload.get("summary") or {}
    rate = reproduction_rate(summary if isinstance(summary, dict) else {})
    run_id = str(
        manifest_entry.get("id")
        or payload.get("run_id")
        or path.parent.name
    )
    timestamp = str(
        manifest_entry.get("executed_at")
        or payload.get("executed_at")
        or ""
    )
    target = str(manifest_entry.get("target") or payload.get("target") or run_id)
    status = str(manifest_entry.get("status") or payload.get("status") or "unknown")
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "benchmark",
        "artifact_path": _rel_path(path if path.suffix == ".json" else path.parent / "benchmark.json", anchor_root),
        "timestamp": timestamp,
        "target": target,
        "run_id": run_id,
        "status": status,
        "metrics": {
            "total": int(summary.get("cases") or 0) or (
                int(summary.get("passed") or 0)
                + int(summary.get("failed") or 0)
                + int(summary.get("timed_out") or 0)
                + int(summary.get("skipped") or 0)
            ),
            "passed": int(summary.get("passed") or 0),
            "failed": int(summary.get("failed") or 0),
            "timed_out": int(summary.get("timed_out") or 0),
            "skipped": int(summary.get("skipped") or 0),
            "reproduction_rate": rate,
            "precision": summary.get("precision"),
            "recall": summary.get("recall"),
        },
        "label": f"{run_id}: {status}",
    }


def normalize_bugbot_training_evidence(*, path: Path, payload: dict[str, Any], anchor_root: Path) -> dict[str, Any]:
    total = int(payload.get("total") or 0)
    passed = int(payload.get("passed") or 0)
    failed = int(payload.get("failed") or 0)
    scenario_pack = str(payload.get("scenario_pack") or "v1")
    timestamp = str(payload.get("timestamp") or "")
    status = "published" if failed == 0 and total > 0 and passed == total else "rejected"
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "bugbot_training",
        "artifact_path": _rel_path(path, anchor_root),
        "timestamp": timestamp,
        "target": f"bugbot-scenario-pack/{scenario_pack}",
        "run_id": path.stem,
        "status": status,
        "metrics": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "proofs": list(payload.get("proofs") or []),
        },
        "label": f"BugBot {scenario_pack}: {passed}/{total} proofs passed",
    }


def normalize_hunt_analysis_evidence(*, path: Path, payload: dict[str, Any], anchor_root: Path) -> dict[str, Any]:
    target_block = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    target_id = str(target_block.get("target_id") or path.stem)
    timestamp = str(payload.get("completed_at") or payload.get("started_at") or "")
    final_status = str(payload.get("final_status") or "unknown")
    stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
    passed = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "PASS")
    failed = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "FAIL")
    skipped = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "SKIP")
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "hunt_analysis",
        "artifact_path": _rel_path(path, anchor_root),
        "timestamp": timestamp,
        "target": target_id,
        "run_id": str(payload.get("analysis_id") or path.stem),
        "status": final_status,
        "metrics": {
            "total": len(stages),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "label": f"{target_id}: {final_status}",
    }


def discover_benchmark_evidence(
    *,
    anchor_root: Path,
    manifest_entries: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in manifest_entries:
        if not (entry.get("artifact_json") or entry.get("record")):
            continue
        normalized = normalize_benchmark_evidence(manifest_entry=entry, anchor_root=anchor_root)
        if normalized:
            rows.append(normalized)
    rows.sort(key=lambda row: _timestamp_sort_key(str(row.get("timestamp", ""))), reverse=True)
    if limit > 0:
        return rows[:limit]
    return rows


def discover_bugbot_training_evidence(*, anchor_root: Path, limit: int) -> list[dict[str, Any]]:
    training_dir = anchor_root / "outcomes" / "training"
    if not training_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(training_dir.glob("*.json"), reverse=True):
        payload = _read_json(path)
        if not payload or payload.get("runner") != "bugbot":
            continue
        rows.append(normalize_bugbot_training_evidence(path=path, payload=payload, anchor_root=anchor_root))
    rows.sort(key=lambda row: _timestamp_sort_key(str(row.get("timestamp", ""))), reverse=True)
    if limit > 0:
        return rows[:limit]
    return rows


def discover_hunt_analysis_evidence(*, anchor_root: Path, limit: int) -> list[dict[str, Any]]:
    analysis_dir = anchor_root / "knowledge" / "analysis"
    if not analysis_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(analysis_dir.glob("*.json"), reverse=True):
        payload = _read_json(path)
        if not payload:
            continue
        if payload.get("record_type") not in {None, "analysis_run"}:
            continue
        rows.append(normalize_hunt_analysis_evidence(path=path, payload=payload, anchor_root=anchor_root))
    rows.sort(key=lambda row: _timestamp_sort_key(str(row.get("timestamp", ""))), reverse=True)
    if limit > 0:
        return rows[:limit]
    return rows


def collect_evidence_records(
    *,
    anchor_root: Path,
    manifest_entries: list[dict[str, Any]] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Merge benchmark, BugBot training, and hunt analysis artifacts (newest first)."""
    per_source = max(limit, 1)
    if manifest_entries is None:
        manifest_entries = []
    rows: list[dict[str, Any]] = []
    rows.extend(
        discover_benchmark_evidence(
            anchor_root=anchor_root,
            manifest_entries=manifest_entries,
            limit=per_source,
        )
    )
    rows.extend(discover_bugbot_training_evidence(anchor_root=anchor_root, limit=per_source))
    rows.extend(discover_hunt_analysis_evidence(anchor_root=anchor_root, limit=per_source))
    rows.sort(key=lambda row: _timestamp_sort_key(str(row.get("timestamp", ""))), reverse=True)
    if limit > 0:
        return rows[:limit]
    return rows


def _format_rate(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.0f}%"


def render_evidence_insights(records: list[dict[str, Any]], *, top_n: int = 5) -> list[str]:
    if not records:
        return ["", "Evidence artifacts", "", "- No structured evidence artifacts found yet."]

    by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in EVIDENCE_KINDS}
    for record in records:
        kind = str(record.get("kind") or "unknown")
        by_kind.setdefault(kind, []).append(record)

    lines = ["", "Evidence artifacts", "", "Source mix"]
    for kind in EVIDENCE_KINDS:
        count = len(by_kind.get(kind, []))
        if count:
            lines.append(f"- {kind}: {count}")

    training = by_kind.get("bugbot_training", [])
    if training:
        latest = training[0]
        metrics = latest.get("metrics") or {}
        lines.extend(
            [
                "",
                "BugBot training (latest)",
                f"- {latest.get('label', latest.get('target', 'bugbot'))} · {latest.get('timestamp', 'unknown')}",
            ]
        )
        if len(training) >= 2:
            previous = training[1]
            prev_metrics = previous.get("metrics") or {}
            delta = int(metrics.get("passed") or 0) - int(prev_metrics.get("passed") or 0)
            if delta:
                direction = "up" if delta > 0 else "down"
                lines.append(f"- proof pass delta vs prior run: {direction} ({delta:+d})")

    benchmarks = by_kind.get("benchmark", [])[:top_n]
    if benchmarks:
        lines.extend(["", "Recent benchmark artifacts"])
        for row in benchmarks:
            metrics = row.get("metrics") or {}
            lines.append(
                f"- {row.get('run_id', row.get('target', 'benchmark'))}: "
                f"pass={metrics.get('passed', '—')} fail={metrics.get('failed', '—')} "
                f"repro={_format_rate(metrics.get('reproduction_rate'))} "
                f"({row.get('timestamp', 'unknown')})"
            )

    hunts = by_kind.get("hunt_analysis", [])[:top_n]
    if hunts:
        lines.extend(["", "Hunt analysis archive"])
        for row in hunts:
            metrics = row.get("metrics") or {}
            lines.append(
                f"- {row.get('label', row.get('target', 'hunt'))}: "
                f"stages pass={metrics.get('passed', '—')} fail={metrics.get('failed', '—')} "
                f"({row.get('timestamp', 'unknown')})"
            )

    return lines
