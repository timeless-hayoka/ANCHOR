"""Cross-model semantic drift helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .parser import Finding


@dataclass
class DriftResult:
    finding_key: str
    before_cluster: int | None
    after_cluster: int | None
    drift_score: float
    moved: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_key": self.finding_key,
            "before_cluster": self.before_cluster,
            "after_cluster": self.after_cluster,
            "drift_score": self.drift_score,
            "moved": self.moved,
            "notes": list(self.notes),
        }


def finding_key(finding: Finding) -> str:
    return f"{finding.tool}:{finding.rule_id}:{finding.file_path}:{finding.start_line}"


def measure_drift(before: list[Finding], after: list[Finding]) -> list[DriftResult]:
    before_index = {finding_key(f): f for f in before}
    after_index = {finding_key(f): f for f in after}
    results: list[DriftResult] = []
    for key in sorted(set(before_index) | set(after_index)):
        lhs = before_index.get(key)
        rhs = after_index.get(key)
        lhs_cluster = (lhs.properties.get("semantic_cluster", {}) if lhs else {}).get("cluster_id")
        rhs_cluster = (rhs.properties.get("semantic_cluster", {}) if rhs else {}).get("cluster_id")
        moved = lhs_cluster != rhs_cluster
        score = 1.0 if moved else 0.0
        if lhs_cluster is None or rhs_cluster is None:
            score *= 0.5
        results.append(
            DriftResult(
                finding_key=key,
                before_cluster=lhs_cluster,
                after_cluster=rhs_cluster,
                drift_score=score,
                moved=moved,
                notes=["Cluster assignment changed" if moved else "Cluster assignment unchanged"],
            )
        )
    return results
