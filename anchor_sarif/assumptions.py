"""Protocol assumption mining helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssumptionCard:
    assumption: str
    evidence: str
    violation_test: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption": self.assumption,
            "evidence": self.evidence,
            "violation_test": self.violation_test,
            "tags": list(self.tags),
        }


_PATTERNS = [
    ("ordering", "Protocol assumes transaction ordering is stable.", "Shuffle execution order and compare outcome."),
    ("liquidation", "Protocol assumes liquidation timing stays favorable.", "Delay or front-run liquidation-triggering actions."),
    ("builder", "Protocol assumes builders maximize protocol-expected inclusion.", "Model builder censorship and selective inclusion."),
    ("oracle", "Protocol assumes price feeds are timely and honest.", "Inject stale or delayed prices and compare state."),
    ("governance", "Protocol assumes parameter changes cannot be gamed.", "Simulate proposal timing and vote concentration."),
]


def extract_protocol_assumptions(text: str, *, limit: int = 5) -> list[AssumptionCard]:
    blob = (text or "").lower()
    cards = [
        AssumptionCard(
            assumption=assumption,
            evidence=f"Matched keyword: {keyword}",
            violation_test=test,
            tags=[keyword],
        )
        for keyword, assumption, test in _PATTERNS
        if keyword in blob
    ]
    if cards:
        return cards[:limit]
    return [
        AssumptionCard(
            assumption="Protocol behavior is stable under adversarial ordering and economic pressure.",
            evidence="Fallback heuristic",
            violation_test="Run current-vs-future simulation with adversarial conditions.",
            tags=["fallback"],
        )
    ]
