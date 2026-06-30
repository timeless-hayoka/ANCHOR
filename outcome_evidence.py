"""Collect and normalize evidence artifacts for outcome insights.

Read-only: discovers JSON on disk, normalizes records, and formats insight lines.
Does not mutate ledger, manifests, or artifact files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anchor_trends import load_benchmark_artifact, parse_iso_timestamp, reproduction_rate, summary_for_entry
from evidence_schema import (
    EVIDENCE_SCHEMA_VERSION,
    benchmark_evidence_status,
    benchmark_target_slug,
    bugbot_proof_gate_status,
    hunt_analysis_evidence_status,
    insight_record_from_canonical,
    is_canonical_evidence,
    normalize_evidence_status,
)

EVIDENCE_KINDS = ("benchmark", "bugbot_training", "hunt_analysis")

EVIDENCE_KIND_LABELS = {
    "benchmark": "Benchmarks",
    "bugbot_training": "BugBot Training",
    "hunt_analysis": "Hunt Analysis",
}


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
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


def _evidence_sort_key(row: dict[str, Any]) -> tuple[float, str, str, str]:
    """Newest first; stable tie-breakers for equal/missing timestamps."""
    return (
        -_timestamp_sort_key(str(row.get("timestamp", ""))),
        str(row.get("run_id", "")),
        str(row.get("kind", "")),
        str(row.get("artifact_path", "")),
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_summary(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_proof_rows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        proof: dict[str, Any] = {}
        if item.get("id") is not None:
            proof["id"] = str(item.get("id"))
        if item.get("result") is not None:
            proof["result"] = str(item.get("result"))
        if item.get("score") is not None:
            proof["score"] = _safe_int(item.get("score"), default=0)
        if proof:
            rows.append(proof)
    return rows


def _is_bugbot_training_artifact(payload: dict[str, Any]) -> bool:
    if is_canonical_evidence(payload):
        return payload.get("kind") == "bugbot_training"
    return payload.get("runner") == "bugbot"


def normalize_bugbot_training_evidence(*, path: Path, payload: dict[str, Any], anchor_root: Path) -> dict[str, Any]:
    if is_canonical_evidence(payload) and payload.get("kind") == "bugbot_training":
        row = insight_record_from_canonical(payload)
        if not row.get("artifact_path"):
            row["artifact_path"] = _rel_path(path, anchor_root)
        return row

    total = _safe_int(payload.get("total"))
    passed = _safe_int(payload.get("passed"))
    failed = _safe_int(payload.get("failed"))
    scenario_pack = str(payload.get("scenario_pack") or "v1")
    timestamp = str(payload.get("timestamp") or "")
    gate = normalize_evidence_status(bugbot_proof_gate_status(total=total, passed=passed, failed=failed))
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "bugbot_training",
        "artifact_path": _rel_path(path, anchor_root),
        "timestamp": timestamp,
        "target": f"bugbot-scenario-pack/{scenario_pack}",
        "run_id": path.stem,
        "status": gate,
        "metrics": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "proofs": _coerce_proof_rows(payload.get("proofs")),
        },
        "links": {},
        "source": {"runner": "bugbot", "scenario_pack": scenario_pack},
        "label": f"BugBot {scenario_pack}: {passed}/{total} curriculum proofs passed",
    }


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
    if not isinstance(payload, dict):
        payload = {}
    if is_canonical_evidence(payload) and payload.get("kind") == "benchmark":
        row = insight_record_from_canonical(payload)
        if not row.get("artifact_path"):
            row["artifact_path"] = _rel_path(path, anchor_root)
        return row

    summary = _coerce_summary(summary_for_entry(manifest_entry, anchor_root))
    if not summary:
        summary = _coerce_summary(payload.get("results_summary") or payload.get("summary"))
    rate = reproduction_rate(summary)
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
    target_source = dict(payload)
    if manifest_entry.get("target"):
        target_source["target"] = manifest_entry.get("target")
    target = benchmark_target_slug(target_source)
    raw_status = str(manifest_entry.get("status") or payload.get("benchmark_status") or payload.get("status") or "unknown")
    passed = _safe_int(summary.get("passed"))
    failed = _safe_int(summary.get("failed"))
    timed_out = _safe_int(summary.get("timed_out"))
    skipped = _safe_int(summary.get("skipped"))
    total = _safe_int(summary.get("cases")) or (passed + failed + timed_out + skipped)
    artifact = path if path.suffix == ".json" else path.parent / "benchmark.json"
    metrics = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "timed_out": timed_out,
        "skipped": skipped,
        "reproduction_rate": rate,
        "precision": summary.get("precision"),
        "recall": summary.get("recall"),
    }
    status = benchmark_evidence_status(raw_status=raw_status, metrics=metrics)
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "benchmark",
        "artifact_path": _rel_path(artifact, anchor_root),
        "timestamp": timestamp,
        "target": target,
        "run_id": run_id,
        "status": status,
        "metrics": metrics,
        "links": {},
        "source": {"benchmark_status": raw_status},
        "label": f"{run_id}: benchmark {status}",
    }


def normalize_hunt_analysis_evidence(*, path: Path, payload: dict[str, Any], anchor_root: Path) -> dict[str, Any]:
    if is_canonical_evidence(payload) and payload.get("kind") == "hunt_analysis":
        row = insight_record_from_canonical(payload)
        if not row.get("artifact_path"):
            row["artifact_path"] = _rel_path(path, anchor_root)
        return row

    target_block = payload.get("analysis_target") if isinstance(payload.get("analysis_target"), dict) else payload.get("target")
    target_id = str(target_block.get("target_id") or path.stem) if isinstance(target_block, dict) else path.stem
    timestamp = str(payload.get("completed_at") or payload.get("started_at") or "")
    final_status = str(payload.get("final_status") or "unknown")
    stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
    passed = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "PASS")
    failed = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "FAIL")
    skipped = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "SKIP")
    status = hunt_analysis_evidence_status(final_status)
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "hunt_analysis",
        "artifact_path": _rel_path(path, anchor_root),
        "timestamp": timestamp,
        "target": target_id,
        "run_id": str(payload.get("analysis_id") or path.stem),
        "status": status,
        "metrics": {
            "total": len(stages),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "links": {},
        "source": {"final_status": final_status},
        "label": f"{target_id}: analysis {status}",
    }


def discover_benchmark_evidence(
    *,
    anchor_root: Path,
    manifest_entries: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in manifest_entries:
        if not isinstance(entry, dict):
            continue
        if not (entry.get("artifact_json") or entry.get("record")):
            continue
        try:
            normalized = normalize_benchmark_evidence(manifest_entry=entry, anchor_root=anchor_root)
        except (TypeError, ValueError, OSError):
            continue
        if normalized:
            rows.append(normalized)
    rows.sort(key=_evidence_sort_key)
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
        if not payload or not _is_bugbot_training_artifact(payload):
            continue
        try:
            rows.append(normalize_bugbot_training_evidence(path=path, payload=payload, anchor_root=anchor_root))
        except (TypeError, ValueError):
            continue
    rows.sort(key=_evidence_sort_key)
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
        try:
            rows.append(normalize_hunt_analysis_evidence(path=path, payload=payload, anchor_root=anchor_root))
        except (TypeError, ValueError):
            continue
    rows.sort(key=_evidence_sort_key)
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
    rows.sort(key=_evidence_sort_key)
    if limit > 0:
        return rows[:limit]
    return rows


def evidence_source_counts(
    *,
    anchor_root: Path,
    manifest_entries: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Count normalized evidence records per source kind (no artificial cap)."""
    manifest_entries = manifest_entries or []
    return {
        "benchmark": len(
            discover_benchmark_evidence(
                anchor_root=anchor_root,
                manifest_entries=manifest_entries,
                limit=0,
            )
        ),
        "bugbot_training": len(
            discover_bugbot_training_evidence(anchor_root=anchor_root, limit=0)
        ),
        "hunt_analysis": len(
            discover_hunt_analysis_evidence(anchor_root=anchor_root, limit=0)
        ),
    }


def build_evidence_dashboard_summary(
    *,
    anchor_root: Path,
    manifest_entries: list[dict[str, Any]] | None = None,
    record_limit: int = 50,
    latest_n: int = 5,
) -> dict[str, Any]:
    """Structured evidence summary for dashboards and API surfaces."""
    manifest_entries = manifest_entries or []
    counts = evidence_source_counts(anchor_root=anchor_root, manifest_entries=manifest_entries)
    records = collect_evidence_records(
        anchor_root=anchor_root,
        manifest_entries=manifest_entries,
        limit=record_limit,
    )
    latest = [
        {
            "kind": str(row.get("kind") or "unknown"),
            "target": str(row.get("target") or ""),
            "status": str(row.get("status") or "unknown"),
            "timestamp": str(row.get("timestamp") or ""),
        }
        for row in records[: max(latest_n, 0)]
    ]
    return {
        "sources": {
            EVIDENCE_KIND_LABELS[kind]: counts.get(kind, 0)
            for kind in EVIDENCE_KINDS
        },
        "latest": latest,
    }


def render_evidence_dashboard_summary(
    *,
    anchor_root: Path,
    manifest_entries: list[dict[str, Any]] | None = None,
    record_limit: int = 50,
    latest_n: int = 5,
) -> list[str]:
    """Render the unified evidence layer for CLI and text dashboards."""
    summary = build_evidence_dashboard_summary(
        anchor_root=anchor_root,
        manifest_entries=manifest_entries,
        record_limit=record_limit,
        latest_n=latest_n,
    )
    lines = ["", "Evidence Sources"]
    for kind in EVIDENCE_KINDS:
        label = EVIDENCE_KIND_LABELS[kind]
        lines.append(f"- {label}: {summary['sources'].get(label, 0)}")
    lines.extend(["", "Latest Evidence"])
    latest = summary.get("latest") or []
    if not latest:
        lines.append("- No structured evidence artifacts found yet.")
    else:
        for row in latest:
            lines.append(
                f"- {row.get('kind', 'unknown')} · {row.get('target', '—')} · "
                f"{row.get('status', 'unknown')} · {row.get('timestamp', 'unknown')}"
            )
    return lines


def render_evidence_dashboard_summary_from_records(
    records: list[dict[str, Any]],
    *,
    source_counts: dict[str, int] | None = None,
    latest_n: int = 5,
) -> list[str]:
    """Render dashboard summary when records and optional counts are already loaded."""
    counts = source_counts or {}
    if not counts:
        by_kind: dict[str, int] = {kind: 0 for kind in EVIDENCE_KINDS}
        for row in records:
            kind = str(row.get("kind") or "unknown")
            if kind in by_kind:
                by_kind[kind] += 1
        counts = by_kind
    lines = ["", "Evidence Sources"]
    for kind in EVIDENCE_KINDS:
        label = EVIDENCE_KIND_LABELS[kind]
        lines.append(f"- {label}: {counts.get(kind, counts.get(label, 0))}")
    lines.extend(["", "Latest Evidence"])
    if not records:
        lines.append("- No structured evidence artifacts found yet.")
    else:
        for row in records[: max(latest_n, 0)]:
            lines.append(
                f"- {row.get('kind', 'unknown')} · {row.get('target', '—')} · "
                f"{row.get('status', 'unknown')} · {row.get('timestamp', 'unknown')}"
            )
    return lines


def _format_rate(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.0f}%"


def render_evidence_insights(records: list[dict[str, Any]], *, top_n: int = 5) -> list[str]:
    if not records:
        return render_evidence_dashboard_summary_from_records([], latest_n=top_n)

    sorted_records = sorted(records, key=_evidence_sort_key)
    source_counts: dict[str, int] = {kind: 0 for kind in EVIDENCE_KINDS}
    for record in sorted_records:
        kind = str(record.get("kind") or "unknown")
        if kind in source_counts:
            source_counts[kind] += 1

    lines = render_evidence_dashboard_summary_from_records(
        sorted_records,
        source_counts=source_counts,
        latest_n=top_n,
    )
    by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in EVIDENCE_KINDS}
    for record in sorted_records:
        kind = str(record.get("kind") or "unknown")
        by_kind.setdefault(kind, []).append(record)

    training = by_kind.get("bugbot_training", [])
    if training:
        latest = training[0]
        metrics = latest.get("metrics") if isinstance(latest.get("metrics"), dict) else {}
        lines.extend(
            [
                "",
                "BugBot training (latest)",
                f"- {latest.get('label', latest.get('target', 'bugbot'))} · {latest.get('timestamp', 'unknown')}",
                f"- proof gate: {latest.get('status', 'unknown')}",
            ]
        )
        if len(training) >= 2:
            previous = training[1]
            prev_metrics = previous.get("metrics") if isinstance(previous.get("metrics"), dict) else {}
            delta = _safe_int(metrics.get("passed")) - _safe_int(prev_metrics.get("passed"))
            if delta:
                direction = "up" if delta > 0 else "down"
                lines.append(f"- curriculum proof pass delta vs prior run: {direction} ({delta:+d})")

    benchmarks = by_kind.get("benchmark", [])[:top_n]
    if benchmarks:
        lines.extend(["", "Recent benchmark artifacts"])
        for row in benchmarks:
            metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
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
            metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
            lines.append(
                f"- {row.get('label', row.get('target', 'hunt'))}: "
                f"stages pass={metrics.get('passed', '—')} fail={metrics.get('failed', '—')} "
                f"({row.get('timestamp', 'unknown')})"
            )

    return lines
