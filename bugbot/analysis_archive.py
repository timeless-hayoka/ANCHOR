"""Archive protected analysis runs via KnowledgePipeline (non-fatal by default)."""

from __future__ import annotations

import logging
from pathlib import Path

from bugbot.analysis import AnalysisConfig, AnalysisExecutionTrace, AnalysisRunResult
from bugbot.analysis_record import build_analysis_record
from knowledge.pipeline import ArchiveResult, KnowledgePipeline

logger = logging.getLogger(__name__)


def archive_target_analysis(
    config: AnalysisConfig,
    result: AnalysisRunResult,
    trace: AnalysisExecutionTrace,
    *,
    pipeline: KnowledgePipeline | None = None,
    knowledge_root: Path | None = None,
    strict_archive: bool = False,
) -> ArchiveResult:
    """Persist an immutable analysis record; does not change analysis success/failure."""
    writer = pipeline or KnowledgePipeline(knowledge_root)
    record = build_analysis_record(config, result, trace)
    archive = writer.archive_analysis_run(record)
    if archive.success:
        logger.info("Archived analysis run: %s", archive.path)
    else:
        message = f"Analysis finished, but archival failed: {archive.error}"
        if strict_archive:
            raise RuntimeError(message)
        logger.warning(message)
    return archive
