"""Canonical evidence record schema for ANCHOR artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
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
        return cls(
            schema_version=str(payload.get("schema_version") or EVIDENCE_SCHEMA_VERSION),
            kind=str(payload.get("kind") or ""),
            artifact_path=str(payload.get("artifact_path") or ""),
            timestamp=str(payload.get("timestamp") or ""),
            target=str(payload.get("target") or ""),
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
