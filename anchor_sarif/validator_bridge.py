"""Bridge between signal filtering and proof-gated validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .economic_context import EconomicContextAssessment, assess_economic_context
from .fp_heuristics import assess_signal_noise, should_drop_signal
from .parser import Finding


@dataclass
class ValidationDecision:
    status: str
    confidence: float
    reasons: list[str]
    future_relevance_score: float = 0.0
    economic_impact_score: float = 0.0
    mev_sensitivity_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "future_relevance_score": self.future_relevance_score,
            "economic_impact_score": self.economic_impact_score,
            "mev_sensitivity_score": self.mev_sensitivity_score,
        }


def validate_candidate(
    finding: Finding,
    *,
    economic_assessment: EconomicContextAssessment | None = None,
    discard_threshold: float = 0.7,
) -> ValidationDecision:
    signal = assess_signal_noise(finding)
    economic = economic_assessment or assess_economic_context(finding)
    reasons = list(signal.get("reasons", [])) + list(economic.notes)
    confidence = max(float(signal.get("confidence", 0.0)), economic.future_relevance_score)

    if signal.get("suggested_action") == "promote" or economic.decision == "promote":
        status = "promote"
    elif should_drop_signal(signal, threshold=discard_threshold) and economic.decision == "reject":
        status = "reject"
    else:
        status = "review"

    return ValidationDecision(
        status=status,
        confidence=round(confidence, 4),
        reasons=reasons,
        future_relevance_score=economic.future_relevance_score,
        economic_impact_score=economic.economic_impact_score,
        mev_sensitivity_score=economic.mev_sensitivity_score,
    )


def annotate_finding(finding: Finding, *, discard_threshold: float = 0.7) -> dict[str, Any]:
    economic = assess_economic_context(finding)
    decision = validate_candidate(finding, economic_assessment=economic, discard_threshold=discard_threshold)
    return {
        "economic_context": economic.to_dict(),
        "validation": decision.to_dict(),
    }
