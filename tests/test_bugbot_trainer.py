from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bugbot.trainer import BugBotTrainer, TrainingRunResult
from knowledge.pipeline import ArchiveResult, KnowledgePipeline


def test_training_succeeds_when_archival_fails(tmp_path: Path) -> None:
    pipeline = MagicMock(spec=KnowledgePipeline)
    pipeline.archive_training_run.return_value = ArchiveResult(
        success=False,
        error="disk full",
    )
    trainer = BugBotTrainer(pipeline=pipeline)
    result = trainer.train([{"id": "s1", "pass": True}])

    assert isinstance(result, TrainingRunResult)
    assert result.success is True
    assert result.scenarios_processed == 1
    assert result.scenarios_passed == 1
    assert result.archive is not None
    assert result.archive.success is False
    pipeline.archive_training_run.assert_called_once()


def test_training_archives_run_on_success(tmp_path: Path) -> None:
    trainer = BugBotTrainer(knowledge_root=tmp_path)
    result = trainer.train(
        [
            {"id": "reentrancy-basic", "pass": True},
            {"id": "oracle-stale", "pass": False},
        ]
    )

    assert result.success is True
    assert result.scenarios_passed == 1
    assert result.archive is not None
    assert result.archive.success is True
    assert result.archive.path is not None
    assert result.archive.path.parent.name == "training"

    payload = result.archive.path.read_text(encoding="utf-8")
    assert "reentrancy-basic" in payload
    assert "scenarios_passed" in payload
