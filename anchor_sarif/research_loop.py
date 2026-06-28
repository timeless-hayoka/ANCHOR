"""Research-loop orchestration helpers for ANCHOR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assumptions import extract_protocol_assumptions
from .economic_context import assess_economic_context
from .future_state import rewrite_findings
from .incentive_surface import map_incentive_surface
from .mev_lifecycle import model_mev_lifecycle
from .parser import Finding
from .universe import compare_universes


@dataclass
class ResearchQueueItem:
    title: str
    priority: float
    reason: str
    evidence_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "priority": self.priority,
            "reason": self.reason,
            "evidence_tags": list(self.evidence_tags),
        }


@dataclass
class ResearchLoopResult:
    rewritten_findings: list[Finding]
    queue: list[ResearchQueueItem]
    assumption_cards: list[dict[str, Any]]
    universe_report: list[dict[str, Any]]
    incentive_surface: list[dict[str, Any]]
    mev_reports: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rewritten_findings": len(self.rewritten_findings),
            "queue": [item.to_dict() for item in self.queue],
            "assumption_cards": list(self.assumption_cards),
            "universe_report": list(self.universe_report),
            "incentive_surface": list(self.incentive_surface),
            "mev_reports": list(self.mev_reports),
        }


def build_research_loop(findings: list[Finding], *, future_state: str = "ePBS + inclusion lists") -> ResearchLoopResult:
    rewritten = rewrite_findings(findings, future_state=future_state)
    queue: list[ResearchQueueItem] = []
    assumption_cards: list[dict[str, Any]] = []
    mev_reports: list[dict[str, Any]] = []

    for finding in rewritten:
        economic = assess_economic_context(finding, future_state=future_state)
        queue.append(
            ResearchQueueItem(
                title=f"{finding.tool}:{finding.rule_id}",
                priority=economic.future_relevance_score,
                reason=economic.decision,
                evidence_tags=[finding.file_path, finding.message[:80]],
            )
        )
        assumption_cards.extend(card.to_dict() for card in extract_protocol_assumptions(finding.message))
        mev_reports.append(model_mev_lifecycle(finding.rule_id).to_dict())

    universe_report = [item.to_dict() for item in compare_universes(findings, future_state=future_state)]
    incentive_surface = [point.to_dict() for point in map_incentive_surface([f.rule_id for f in findings[:5]])]
    queue.sort(key=lambda item: item.priority, reverse=True)
    return ResearchLoopResult(
        rewritten_findings=rewritten,
        queue=queue,
        assumption_cards=assumption_cards,
        universe_report=universe_report,
        incentive_surface=incentive_surface,
        mev_reports=mev_reports,
    )
