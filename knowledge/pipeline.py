"""Archive BugBot training runs and detector artifacts into the knowledge corpus."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence_schema import enrich_hunt_analysis_artifact

logger = logging.getLogger(__name__)

_SCENARIO_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


@dataclass(frozen=True)
class ArchiveResult:
    success: bool
    path: Path | None = None
    error: str | None = None


def default_knowledge_root() -> Path:
    """Return knowledge root based on ANCHOR_ROOT or the ANCHOR repo layout."""
    anchor_root = os.environ.get("ANCHOR_ROOT", "").strip()
    if anchor_root:
        return (Path(anchor_root).expanduser().resolve() / "knowledge")
    return (Path(__file__).resolve().parent).resolve()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _validate_scenario_id(scenario_id: str) -> str:
    cleaned = scenario_id.strip()
    if not cleaned or not _SCENARIO_ID_RE.fullmatch(cleaned):
        raise ValueError(
            "Scenario id must be 1-128 chars: letters, digits, '.', '_', or '-'"
        )
    return cleaned


class KnowledgeWriter:
    """Write training runs, detector results, and scenarios into the knowledge corpus."""

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self.knowledge_root = (knowledge_root or default_knowledge_root()).resolve()
        try:
            self.knowledge_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"Failed to create knowledge root directory {self.knowledge_root}: {exc}"
            logger.error(msg)
            raise OSError(msg) from exc

    def write_training_run(self, run_data: dict[str, Any]) -> ArchiveResult:
        """Write a complete training run to the corpus."""
        try:
            run_id = f"training-run-{_utc_stamp()}"
            path = self.knowledge_root / "training" / f"{run_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(run_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info("[Knowledge] Training run archived: %s", path)
            return ArchiveResult(success=True, path=path)
        except TypeError as exc:
            msg = f"JSON serialization error while writing training run: {exc}"
            logger.error(msg)
            return ArchiveResult(success=False, error=msg)
        except OSError as exc:
            msg = f"Failed to write training run: {exc}"
            logger.error(msg)
            return ArchiveResult(success=False, error=msg)

    def write_detector_result(
        self, detector_name: str, result: dict[str, Any]
    ) -> ArchiveResult:
        """Write a single detector result."""
        label = detector_name.strip()
        if not label:
            return ArchiveResult(success=False, error="detector_name must be non-empty")
        safe_name = re.sub(r"[^\w.-]+", "-", label).strip("-") or "detector"
        try:
            path = self.knowledge_root / "detectors" / f"{safe_name}-{_utc_stamp()}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info("[Knowledge] Detector result archived: %s", path)
            return ArchiveResult(success=True, path=path)
        except (TypeError, OSError) as exc:
            msg = f"Failed to write detector result for {label}: {exc}"
            logger.error(msg)
            return ArchiveResult(success=False, error=msg)

    def write_scenario(self, scenario: dict[str, Any]) -> ArchiveResult:
        """Write a scenario definition."""
        try:
            raw_id = scenario.get("id")
            if not isinstance(raw_id, str):
                raise ValueError("Scenario must have a string 'id' field")
            scenario_id = _validate_scenario_id(raw_id)
            path = self.knowledge_root / "scenarios" / f"{scenario_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(scenario, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info("[Knowledge] Scenario archived: %s", path)
            return ArchiveResult(success=True, path=path)
        except (TypeError, ValueError, OSError) as exc:
            sid = scenario.get("id", "unknown") if isinstance(scenario, dict) else "unknown"
            msg = f"Failed to write scenario {sid}: {exc}"
            logger.error(msg)
            return ArchiveResult(success=False, error=msg)

    def write_analysis_run(self, run_data: dict[str, Any]) -> ArchiveResult:
        """
        Archive an analysis run record in the knowledge corpus.
        
        Parameters:
            run_data (dict[str, Any]): Analysis run data to archive.
        
        Returns:
            ArchiveResult: Success details including the written path, or an error message on failure.
        """
        try:
            analysis_id = run_data.get("analysis_id")
            if isinstance(analysis_id, str) and analysis_id.strip():
                filename = f"{analysis_id.strip()}.json"
            else:
                filename = f"analysis-run-{_utc_stamp()}.json"
            path = self.knowledge_root / "analysis" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = dict(run_data)
            payload["analysis_id"] = path.stem
            artifact_paths = dict(payload.get("artifact_paths") or {})
            artifact_paths["archive_record"] = str(path)
            payload["artifact_paths"] = artifact_paths
            anchor_root = self.knowledge_root.parent
            try:
                rel_artifact_path = str(path.resolve().relative_to(anchor_root.resolve()))
            except ValueError:
                rel_artifact_path = str(path)
            payload = enrich_hunt_analysis_artifact(payload, artifact_path=rel_artifact_path)
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info("[Knowledge] Analysis run archived: %s", path)
            return ArchiveResult(success=True, path=path)
        except TypeError as exc:
            msg = f"JSON serialization error while writing analysis run: {exc}"
            logger.error(msg)
            return ArchiveResult(success=False, error=msg)
        except OSError as exc:
            msg = f"Failed to write analysis run: {exc}"
            logger.error(msg)
            return ArchiveResult(success=False, error=msg)


class KnowledgePipeline:
    """High-level pipeline for BugBot → knowledge archival with graceful degradation."""

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self.writer = KnowledgeWriter(knowledge_root)

    def archive_training_run(self, run_data: dict[str, Any]) -> ArchiveResult:
        return self.writer.write_training_run(run_data)

    def archive_detector_result(
        self, detector_name: str, result: dict[str, Any]
    ) -> ArchiveResult:
        return self.writer.write_detector_result(detector_name, result)

    def archive_scenario(self, scenario: dict[str, Any]) -> ArchiveResult:
        return self.writer.write_scenario(scenario)

    def archive_analysis_run(self, run_data: dict[str, Any]) -> ArchiveResult:
        return self.writer.write_analysis_run(run_data)
