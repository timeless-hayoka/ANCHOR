"""Canonical evidence record schema for ANCHOR artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVIDENCE_SCHEMA_VERSION = "1.0"

EVIDENCE_KINDS = frozenset({"benchmark", "bugbot_training", "hunt_analysis"})

EVIDENCE_STATUSES = frozenset(
    {
        "proof_gate_passed",
        "proof_gate_failed",
        "published",
        "rejected",
        "unknown",
    }
)

LEGACY_STATUS_ALIASES = {
    "proof_gate_pass": "proof_gate_passed",
    "proof_gate_fail": "proof_gate_failed",
    "proof_gate_partial": "proof_gate_failed",
}

CANONICAL_REQUIRED_FIELDS = (
    "schema_version",
    "kind",
    "artifact_path",
    "timestamp",
    "target",
    "run_id",
    "status",
    "metrics",
    "links",
    "source",
)


@dataclass(frozen=True)
class EvidenceRecord:
    schema_version: str
    kind: str
    artifact_path: str
    timestamp: str
    target: str
    run_id: str
    status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    links: dict[str, str] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "artifact_path": self.artifact_path,
            "timestamp": self.timestamp,
            "target": self.target,
            "run_id": self.run_id,
            "status": normalize_evidence_status(self.status),
            "metrics": dict(self.metrics),
            "links": dict(self.links),
            "source": dict(self.source),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceRecord:
        metrics = payload.get("metrics")
        links = payload.get("links")
        source = payload.get("source")
        target_raw = payload.get("target")
        if isinstance(target_raw, str) and target_raw.strip():
            target = target_raw.strip()
        else:
            target = str(payload.get("evidence_target") or "")
        return cls(
            schema_version=str(payload.get("schema_version") or EVIDENCE_SCHEMA_VERSION),
            kind=str(payload.get("kind") or ""),
            artifact_path=str(payload.get("artifact_path") or ""),
            timestamp=str(payload.get("timestamp") or ""),
            target=target,
            run_id=str(payload.get("run_id") or ""),
            status=normalize_evidence_status(str(payload.get("status") or "unknown")),
            metrics=dict(metrics) if isinstance(metrics, dict) else {},
            links={str(k): str(v) for k, v in links.items()} if isinstance(links, dict) else {},
            source=dict(source) if isinstance(source, dict) else {},
        )


def normalize_evidence_status(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "unknown"
    lowered = cleaned.lower()
    if lowered in EVIDENCE_STATUSES:
        return lowered
    return LEGACY_STATUS_ALIASES.get(lowered, "unknown")


def is_canonical_evidence(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("schema_version")) != EVIDENCE_SCHEMA_VERSION:
        return False
    for key in CANONICAL_REQUIRED_FIELDS:
        if key not in payload:
            return False
    if str(payload.get("kind")) not in EVIDENCE_KINDS:
        return False
    if not isinstance(payload.get("metrics"), dict):
        return False
    if not isinstance(payload.get("links"), dict):
        return False
    if not isinstance(payload.get("source"), dict):
        return False
    target = payload.get("target")
    evidence_target = payload.get("evidence_target")
    has_target = (isinstance(target, str) and bool(target.strip())) or (
        isinstance(evidence_target, str) and bool(evidence_target.strip())
    )
    if not has_target:
        return False
    return normalize_evidence_status(str(payload.get("status"))) in EVIDENCE_STATUSES


def bugbot_proof_gate_status(*, total: int, passed: int, failed: int) -> str:
    if total > 0 and failed == 0 and passed == total:
        return "proof_gate_passed"
    if total > 0 and passed > 0 and passed < total:
        return "proof_gate_failed"
    if total > 0 and passed == 0:
        return "proof_gate_failed"
    return "proof_gate_failed"


def merge_legacy_bugbot_fields(
    canonical: dict[str, Any],
    *,
    scenario_pack: str,
    total: int,
    passed: int,
    failed: int,
    proofs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preserve pre-schema BugBot keys for downstream tools that still expect them."""
    merged = dict(canonical)
    merged.update(
        {
            "runner": "bugbot",
            "scenario_pack": scenario_pack,
            "total": total,
            "passed": passed,
            "failed": failed,
            "proofs": proofs,
        }
    )
    return merged


def build_bugbot_training_record(
    *,
    artifact_path: str,
    timestamp: str,
    run_id: str,
    scenario_pack: str,
    total: int,
    passed: int,
    failed: int,
    proofs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Emit canonical EvidenceRecord JSON with legacy BugBot fields attached."""
    status = bugbot_proof_gate_status(total=total, passed=passed, failed=failed)
    record = EvidenceRecord(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        kind="bugbot_training",
        artifact_path=artifact_path,
        timestamp=timestamp,
        target=f"bugbot-scenario-pack/{scenario_pack}",
        run_id=run_id,
        status=status,
        metrics={
            "total": total,
            "passed": passed,
            "failed": failed,
            "proofs": proofs,
        },
        links={},
        source={"runner": "bugbot", "scenario_pack": scenario_pack},
    )
    return merge_legacy_bugbot_fields(
        record.to_dict(),
        scenario_pack=scenario_pack,
        total=total,
        passed=passed,
        failed=failed,
        proofs=proofs,
    )


def insight_label_for_record(record: dict[str, Any]) -> str:
    kind = str(record.get("kind") or "")
    target = str(record.get("target") or "")
    metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
    if kind == "bugbot_training":
        scenario_pack = str((record.get("source") or {}).get("scenario_pack") or "v1")
        passed = int(metrics.get("passed") or 0)
        total = int(metrics.get("total") or 0)
        return f"BugBot {scenario_pack}: {passed}/{total} curriculum proofs passed"
    if kind == "benchmark":
        return f"{record.get('run_id', target)}: benchmark {record.get('status', 'unknown')}"
    if kind == "hunt_analysis":
        return f"{target}: analysis {record.get('status', 'unknown')}"
    return target or str(record.get("run_id") or "evidence")


def insight_record_from_canonical(payload: dict[str, Any]) -> dict[str, Any]:
    """Map canonical artifact JSON to outcome-insights view model."""
    record = EvidenceRecord.from_dict(payload)
    row = record.to_dict()
    row["label"] = insight_label_for_record(row)
    return row


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_summary_dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _reproduction_rate(summary: dict[str, Any]) -> float | None:
    passed = _safe_int(summary.get("passed"))
    failed = _safe_int(summary.get("failed"))
    timed_out = _safe_int(summary.get("timed_out"))
    skipped = _safe_int(summary.get("skipped"))
    total = passed + failed + timed_out + skipped
    if total <= 0:
        return None
    return passed / total


def benchmark_target_slug(payload: dict[str, Any]) -> str:
    target = payload.get("target")
    if isinstance(target, str) and target.strip():
        return target.strip()
    if isinstance(target, dict):
        for key in ("repo", "target_id", "name"):
            value = target.get(key)
            if isinstance(value, str) and value.strip():
                cleaned = value.strip()
                if "/" in cleaned:
                    return Path(cleaned).name
                return cleaned
    benchmark_id = payload.get("benchmark_id")
    if isinstance(benchmark_id, str) and benchmark_id.strip():
        return benchmark_id.strip()
    run_id = payload.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return "benchmark"


def benchmark_evidence_status(*, raw_status: str, metrics: dict[str, Any]) -> str:
    status = str(raw_status or "").strip().lower()
    failed = _safe_int(metrics.get("failed"))
    timed_out = _safe_int(metrics.get("timed_out"))
    if status in {"complete", "published", "scaffold"}:
        if failed == 0 and timed_out == 0:
            return "published"
        return "rejected"
    if status in {"failed", "incomplete", "rejected"}:
        return "rejected"
    return "unknown"


def hunt_analysis_evidence_status(final_status: str) -> str:
    status = str(final_status or "").strip().upper()
    if status == "PASS":
        return "published"
    if status in {"FAILED", "BLOCKED"}:
        return "rejected"
    return "unknown"


def merge_canonical_evidence(canonical: dict[str, Any], legacy: dict[str, Any]) -> dict[str, Any]:
    """Overlay canonical evidence fields while preserving conflicting legacy keys."""
    merged = dict(legacy)
    legacy_schema = legacy.get("schema_version")
    if legacy_schema is not None and legacy_schema != canonical.get("schema_version"):
        merged["benchmark_schema_version"] = legacy_schema
        merged["analysis_schema_version"] = legacy_schema
    if legacy.get("status") is not None and legacy.get("status") != canonical.get("status"):
        merged["benchmark_status"] = legacy.get("status")
    legacy_target = legacy.get("target")
    preserve_target_dict = isinstance(legacy_target, dict)
    if legacy_target is not None and legacy_target != canonical.get("target") and not preserve_target_dict:
        merged["benchmark_target"] = legacy_target
        merged["analysis_target"] = legacy_target
    if preserve_target_dict:
        merged["analysis_target"] = legacy_target
        merged["benchmark_target"] = legacy_target
        merged["evidence_target"] = canonical["target"]
    if legacy.get("final_status") is not None:
        merged["final_status"] = legacy.get("final_status")
    for key in CANONICAL_REQUIRED_FIELDS:
        if key == "target" and preserve_target_dict:
            merged["evidence_target"] = canonical["target"]
            continue
        merged[key] = canonical[key]
    if preserve_target_dict:
        merged["target"] = legacy_target
    return merged


def build_benchmark_evidence_record(
    *,
    artifact_path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    summary = _coerce_summary_dict(payload.get("results_summary") or payload.get("summary"))
    passed = _safe_int(summary.get("passed"))
    failed = _safe_int(summary.get("failed"))
    timed_out = _safe_int(summary.get("timed_out"))
    skipped = _safe_int(summary.get("skipped"))
    total = _safe_int(summary.get("cases")) or (passed + failed + timed_out + skipped)
    metrics = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "timed_out": timed_out,
        "skipped": skipped,
        "reproduction_rate": _reproduction_rate(summary),
        "precision": summary.get("precision"),
        "recall": summary.get("recall"),
    }
    raw_status = str(payload.get("benchmark_status") or payload.get("status") or "unknown")
    status = benchmark_evidence_status(raw_status=raw_status, metrics=metrics)
    run_id = str(payload.get("run_id") or Path(artifact_path).parent.name)
    timestamp = str(payload.get("executed_at") or "")
    target = benchmark_target_slug(payload)
    links: dict[str, str] = {}
    for key in ("artifact_json", "metrics_json", "record"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            links[key] = value.strip()
    source = {
        "benchmark_id": payload.get("benchmark_id"),
        "level": payload.get("level"),
        "benchmark_status": raw_status,
    }
    record = EvidenceRecord(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        kind="benchmark",
        artifact_path=artifact_path,
        timestamp=timestamp,
        target=target,
        run_id=run_id,
        status=status,
        metrics=metrics,
        links=links,
        source={k: v for k, v in source.items() if v is not None},
    )
    return record.to_dict()


def enrich_benchmark_artifact(payload: dict[str, Any], *, artifact_path: str) -> dict[str, Any]:
    """Attach canonical evidence fields to a benchmark.json payload at write time."""
    canonical = build_benchmark_evidence_record(artifact_path=artifact_path, payload=payload)
    return merge_canonical_evidence(canonical, payload)


def build_hunt_analysis_evidence_record(
    *,
    artifact_path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    target_block = payload.get("analysis_target") if isinstance(payload.get("analysis_target"), dict) else payload.get("target")
    target_id = ""
    if isinstance(target_block, dict):
        target_id = str(target_block.get("target_id") or "")
    if not target_id:
        target_id = Path(artifact_path).stem
    timestamp = str(payload.get("completed_at") or payload.get("started_at") or "")
    final_status = str(payload.get("final_status") or "unknown")
    stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
    passed = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "PASS")
    failed = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "FAIL")
    skipped = sum(1 for stage in stages if isinstance(stage, dict) and stage.get("outcome") == "SKIP")
    record = EvidenceRecord(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        kind="hunt_analysis",
        artifact_path=artifact_path,
        timestamp=timestamp,
        target=target_id,
        run_id=str(payload.get("analysis_id") or Path(artifact_path).stem),
        status=hunt_analysis_evidence_status(final_status),
        metrics={
            "total": len(stages),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        links={},
        source={"record_type": payload.get("record_type"), "final_status": final_status},
    )
    return record.to_dict()


def enrich_hunt_analysis_artifact(payload: dict[str, Any], *, artifact_path: str) -> dict[str, Any]:
    """Attach canonical evidence fields to a hunt analysis archive at write time."""
    canonical = build_hunt_analysis_evidence_record(artifact_path=artifact_path, payload=payload)
    return merge_canonical_evidence(canonical, payload)
