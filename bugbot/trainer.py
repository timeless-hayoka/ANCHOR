"""Run BugBot training sessions and optionally archive results to the knowledge corpus."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from knowledge.pipeline import ArchiveResult, KnowledgePipeline

logger = logging.getLogger(__name__)

TrainStep = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class TrainingRunResult:
    """Outcome of a training run (training logic, not archival)."""

    success: bool
    scenarios_processed: int
    scenarios_passed: int
    archive: ArchiveResult | None = None
    error: str | None = None


def _default_train_step(scenario: dict[str, Any]) -> bool:
    """Minimal pass/fail check until real trainer logic is wired."""
    if scenario.get("pass") is True:
        return True
    if scenario.get("expected_outcome") == "pass":
        return True
    return False


class BugBotTrainer:
    """
    Pedagogical trainer: training succeeds or fails on training logic;
    knowledge archival succeeds or fails separately (non-fatal by default).
    """

    def __init__(
        self,
        pipeline: KnowledgePipeline | None = None,
        *,
        knowledge_root: Path | None = None,
        strict_archive: bool = False,
        train_step: TrainStep | None = None,
    ) -> None:
        self.pipeline = pipeline or KnowledgePipeline(knowledge_root)
        self.strict_archive = strict_archive
        self._train_step = train_step or _default_train_step

    def train(self, scenarios: list[dict[str, Any]]) -> TrainingRunResult:
        """Run scenarios, then archive run metadata without failing training on archive errors."""
        try:
            passed = 0
            results: list[dict[str, Any]] = []
            for scenario in scenarios:
                ok = self._train_step(scenario)
                if ok:
                    passed += 1
                sid = scenario.get("id", "unknown")
                results.append({"id": sid, "passed": ok})

            run_data = {
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "scenario_count": len(scenarios),
                "scenarios_passed": passed,
                "scenarios_failed": len(scenarios) - passed,
                "results": results,
            }
            archive = self._archive_training_run(run_data)
            return TrainingRunResult(
                success=True,
                scenarios_processed=len(scenarios),
                scenarios_passed=passed,
                archive=archive,
            )
        except RuntimeError:
            raise
        except Exception as exc:
            logger.exception("Training run failed")
            return TrainingRunResult(
                success=False,
                scenarios_processed=len(scenarios),
                scenarios_passed=0,
                archive=None,
                error=str(exc),
            )

    def _archive_training_run(self, run_data: dict[str, Any]) -> ArchiveResult:
        result = self.pipeline.archive_training_run(run_data)
        if result.success:
            logger.info("Archived training run: %s", result.path)
        else:
            message = f"Training completed, but archival failed: {result.error}"
            if self.strict_archive:
                raise RuntimeError(message)
            logger.warning(message)
        return result
