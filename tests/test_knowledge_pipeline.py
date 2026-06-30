from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from knowledge.pipeline import (
    ArchiveResult,
    KnowledgePipeline,
    KnowledgeWriter,
    default_knowledge_root,
)


def test_default_knowledge_root_honors_anchor_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = tmp_path / "ANCHOR"
    anchor.mkdir()
    monkeypatch.setenv("ANCHOR_ROOT", str(anchor))
    assert default_knowledge_root() == (anchor / "knowledge").resolve()


def test_write_training_run_returns_archive_result(tmp_path: Path) -> None:
    writer = KnowledgeWriter(tmp_path)
    result = writer.write_training_run({"epochs": 1, "loss": 0.12})
    assert isinstance(result, ArchiveResult)
    assert result.success is True
    assert result.path is not None
    assert result.path.parent.name == "training"
    payload = json.loads(result.path.read_text(encoding="utf-8"))
    assert payload["epochs"] == 1


def test_write_scenario_requires_valid_id(tmp_path: Path) -> None:
    writer = KnowledgeWriter(tmp_path)
    bad = writer.write_scenario({"id": "../escape"})
    assert bad.success is False
    assert bad.error

    good = writer.write_scenario({"id": "reentrancy-basic", "steps": []})
    assert good.success is True
    assert good.path == tmp_path / "scenarios" / "reentrancy-basic.json"


def test_write_detector_result_sanitizes_name(tmp_path: Path) -> None:
    writer = KnowledgeWriter(tmp_path)
    result = writer.write_detector_result("slither/reentrancy", {"hits": 2})
    assert result.success is True
    assert result.path is not None
    assert result.path.name.startswith("slither-reentrancy-")


def test_pipeline_does_not_raise_on_serialization_error(tmp_path: Path) -> None:
    pipeline = KnowledgePipeline(tmp_path)
    result = pipeline.archive_training_run({"bad": {1, 2, 3}})  # type: ignore[arg-type]
    assert result.success is False
    assert result.error


def test_knowledge_root_env_used_by_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = tmp_path / "repo"
    knowledge = anchor / "knowledge"
    monkeypatch.setenv("ANCHOR_ROOT", str(anchor))
    pipeline = KnowledgePipeline()
    result = pipeline.archive_scenario({"id": "dvd-unstoppable", "target": "dvd"})
    assert result.success is True
    assert result.path is not None
    assert result.path.parent == knowledge / "scenarios"
