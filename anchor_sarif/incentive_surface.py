"""Incentive-surface mapping helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .mev_lifecycle import model_mev_lifecycle


@dataclass
class IncentiveSurfacePoint:
    name: str
    current_risk: float
    future_risk: float
    pressure: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "current_risk": self.current_risk,
            "future_risk": self.future_risk,
            "pressure": self.pressure,
            "notes": list(self.notes),
        }


def map_incentive_surface(techniques: list[str]) -> list[IncentiveSurfacePoint]:
    points: list[IncentiveSurfacePoint] = []
    for technique in techniques:
        lifecycle = model_mev_lifecycle(technique)
        future_risk = 0.7 if "less reliable" in lifecycle.future_world else 0.5
        current_risk = 0.6 if "reliable" in lifecycle.current_world else 0.4
        points.append(
            IncentiveSurfacePoint(
                name=technique,
                current_risk=current_risk,
                future_risk=future_risk,
                pressure=lifecycle.disruption,
                notes=[lifecycle.current_world, lifecycle.future_world],
            )
        )
    return points
