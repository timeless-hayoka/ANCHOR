"""Parallel-universe simulation helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .parser import Finding
from .future_state import rewrite_findings
from .economic_context import assess_economic_context


@dataclass
class UniverseComparison:
    finding_key: str
    current_relevance: float
    future_relevance: float
    delta: float
    current_decision: str
    future_decision: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_key": self.finding_key,
            "current_relevance": self.current_relevance,
            "future_relevance": self.future_relevance,
            "delta": self.delta,
            "current_decision": self.current_decision,
            "future_decision": self.future_decision,
            "notes": list(self.notes),
        }


def _finding_key(finding: Finding) -> str:
    return f"{finding.tool}:{finding.rule_id}:{finding.file_path}:{finding.start_line}"


def compare_universes(findings: list[Finding], *, future_state: str = "ePBS + inclusion lists") -> list[UniverseComparison]:
    rewritten = rewrite_findings(findings, future_state=future_state)
    results: list[UniverseComparison] = []
    for original, future in zip(findings, rewritten):
        current = assess_economic_context(original, future_state=None)
        future_assessment = assess_economic_context(future, future_state=future_state)
        results.append(
            UniverseComparison(
                finding_key=_finding_key(original),
                current_relevance=current.future_relevance_score,
                future_relevance=future_assessment.future_relevance_score,
                delta=round(future_assessment.future_relevance_score - current.future_relevance_score, 4),
                current_decision=current.decision,
                future_decision=future_assessment.decision,
                notes=[f"Compared {future_state} against current state"],
            )
        )
    return results
