"""Economic context scoring helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .parser import Finding


@dataclass
class EconomicContextAssessment:
    future_relevance_score: float
    economic_impact_score: float
    mev_sensitivity_score: float
    notes: list[str] = field(default_factory=list)
    decision: str = "review"

    def to_dict(self) -> dict[str, Any]:
        return {
            "future_relevance_score": self.future_relevance_score,
            "economic_impact_score": self.economic_impact_score,
            "mev_sensitivity_score": self.mev_sensitivity_score,
            "notes": list(self.notes),
            "decision": self.decision,
        }


_KEYWORDS = {
    "mev": 0.3,
    "sandwich": 0.35,
    "front-run": 0.35,
    "front run": 0.35,
    "back-run": 0.2,
    "back run": 0.2,
    "liquidation": 0.25,
    "oracle": 0.2,
    "inclusion list": 0.35,
    "ordering": 0.2,
    "censor": 0.2,
    "grief": 0.2,
    "timing": 0.15,
    "auction": 0.15,
}


def assess_economic_context(
    finding: Finding,
    *,
    future_state: str | None = None,
    protocol_context: str | None = None,
) -> EconomicContextAssessment:
    blob = " ".join(
        part for part in [
            finding.rule_id,
            finding.message,
            finding.snippet or "",
            str((finding.normalized or {}).get("category", "")),
            protocol_context or "",
            future_state or str((finding.properties or {}).get("future_state", {}).get("future_state", "")),
        ]
        if part
    ).lower()

    mev = 0.1
    impact = 0.1
    notes: list[str] = []
    for needle, weight in _KEYWORDS.items():
        if needle in blob:
            mev = min(1.0, mev + weight)
            impact = min(1.0, impact + weight * 0.9)
            notes.append(f"Matched economic keyword: {needle}")

    if future_state:
        notes.append(f"Evaluated under future state: {future_state}")
        mev = min(1.0, mev + 0.1)
        impact = min(1.0, impact + 0.1)

    future_relevance = min(1.0, round((mev + impact) / 2.0, 4))
    if future_relevance >= 0.75:
        decision = "promote"
    elif future_relevance >= 0.45:
        decision = "review"
    else:
        decision = "reject"

    return EconomicContextAssessment(
        future_relevance_score=future_relevance,
        economic_impact_score=round(impact, 4),
        mev_sensitivity_score=round(mev, 4),
        notes=notes or ["No strong economic signal"],
        decision=decision,
    )
