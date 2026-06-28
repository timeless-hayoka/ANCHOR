"""Future-state rewriting helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .parser import Finding


@dataclass
class FutureStateRewrite:
    original_message: str
    rewritten_message: str
    future_state: str
    reason: str
    confidence: float = 0.5
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_message": self.original_message,
            "rewritten_message": self.rewritten_message,
            "future_state": self.future_state,
            "reason": self.reason,
            "confidence": self.confidence,
            "tags": list(self.tags),
        }


def rewrite_finding(
    finding: Finding,
    *,
    future_state: str = "ePBS + inclusion lists",
    reason: str | None = None,
) -> Finding:
    note = reason or f"Rewritten for {future_state} assumptions"
    metadata = dict(finding.properties or {})
    metadata["future_state"] = {
        "future_state": future_state,
        "reason": note,
        "original_message": finding.message,
        "rewritten_message": finding.message,
    }
    metadata.setdefault("tags", [])
    if isinstance(metadata["tags"], list) and "future-state" not in metadata["tags"]:
        metadata["tags"].append("future-state")
    return replace(finding, properties=metadata)


def rewrite_findings(
    findings: list[Finding],
    *,
    future_state: str = "ePBS + inclusion lists",
    reason: str | None = None,
) -> list[Finding]:
    return [rewrite_finding(finding, future_state=future_state, reason=reason) for finding in findings]
