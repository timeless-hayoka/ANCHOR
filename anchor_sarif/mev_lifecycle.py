"""MEV lifecycle modeling helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MevLifecycleReport:
    technique: str
    current_world: str
    future_world: str
    disruption: str
    new_attack_vectors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique": self.technique,
            "current_world": self.current_world,
            "future_world": self.future_world,
            "disruption": self.disruption,
            "new_attack_vectors": list(self.new_attack_vectors),
        }


_LIFECYCLE = {
    "sandwich": (
        "reliable under current ordering assumptions",
        "less reliable under inclusion lists and forced ordering",
        "forced space pressure, inclusion-list spam, displaced back-runs",
    ),
    "front-run": (
        "common in public mempool competition",
        "harder when ordering is constrained by protocol rules",
        "timing attacks around list publication",
    ),
    "liquidation": (
        "depends on latency and ordering",
        "sensitive to forced inclusion and delayed execution",
        "cross-slot liquidation races and griefing",
    ),
    "oracle": (
        "benefits from predictable update timing",
        "exposed to stale or delayed updates under new rules",
        "oracle delay gaming and stale-price exploitation",
    ),
}


def model_mev_lifecycle(technique: str) -> MevLifecycleReport:
    key = technique.lower().strip()
    current, future, disruption = _LIFECYCLE.get(
        key,
        (
            "stable in the current mempool model",
            "unmodeled under the future state",
            "requires scenario-specific evaluation",
        ),
    )
    return MevLifecycleReport(
        technique=technique,
        current_world=current,
        future_world=future,
        disruption=disruption,
        new_attack_vectors=["scenario-specific follow-up"],
    )
