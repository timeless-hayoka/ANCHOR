"""Build immutable analysis run records for knowledge archival."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from bugbot.analysis import (
    AnalysisConfig,
    AnalysisExecutionTrace,
    AnalysisRunResult,
    AnalysisStageResult,
)
from bugbot.scope import (
    IDENTITY_VERIFIED_REPO,
    ScopeGrant,
    active_grant_path,
)

ANALYSIS_RECORD_SCHEMA_VERSION = "1.0"
FINAL_STATUS_PASS = "PASS"
FINAL_STATUS_BLOCKED = "BLOCKED"
FINAL_STATUS_FAILED = "FAILED"
FINAL_STATUS_PARTIAL = "PARTIAL"


def derive_final_status(result: AnalysisRunResult) -> str:
    if result.blocked:
        return FINAL_STATUS_BLOCKED
    if result.success:
        return FINAL_STATUS_PASS
    stages = {stage.stage: stage for stage in result.stages}
    if stages.get("identity") and stages["identity"].success:
        return FINAL_STATUS_PARTIAL
    return FINAL_STATUS_FAILED


def _stage_outcome(stage: AnalysisStageResult) -> str:
    if stage.skipped:
        return "SKIP"
    return "PASS" if stage.success else "FAIL"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _tool_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name, args in (("git", ["--version"]), ("forge", ["--version"])):
        binary = shutil.which(name)
        if not binary:
            versions[name] = None
            continue
        proc = subprocess.run(
            [binary, *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            versions[name] = None
            continue
        line = (proc.stdout or proc.stderr or "").strip().splitlines()
        versions[name] = line[0] if line else None
    return versions


def _scope_dir_for_config(config: AnalysisConfig) -> Path:
    anchor_root = (config.anchor_root or Path.cwd()).resolve()
    return anchor_root / "scope"


def _execution_environment(
    config: AnalysisConfig,
    result: AnalysisRunResult,
) -> dict[str, Any]:
    anchor_root = (config.anchor_root or Path.cwd()).resolve()
    workspace = result.workspace.resolve()
    isolated = config.grant.identity_status == IDENTITY_VERIFIED_REPO
    disposable = False
    if isolated:
        analysis_root = (anchor_root / "scope" / "analysis").resolve()
        try:
            workspace.relative_to(analysis_root)
            disposable = True
        except ValueError:
            disposable = False
    sandbox_home = workspace / ".sandbox-home" if isolated else None
    return {
        "workspace": str(workspace),
        "anchor_root": str(anchor_root),
        "isolated_execution": isolated,
        "disposable_workspace": disposable,
        "sandbox_home": str(sandbox_home) if sandbox_home else None,
        "network_offline_for_tests": True,
    }


def _serialize_grant_reference(grant: ScopeGrant, grant_path: Path) -> dict[str, Any]:
    return {
        "active_grant_path": str(grant_path),
        "schema_version": grant.schema_version,
        "confirmation_source": grant.confirmation_source,
        "reviewer_decision": grant.reviewer_decision,
        "reviewed_at": grant.reviewed_at.isoformat(),
        "scope_policy_url": grant.scope_policy_url,
        "permitted_actions": list(grant.permitted_actions),
        "prohibited_actions": list(grant.prohibited_actions),
        "disclosure_channel": grant.disclosure_channel,
        "evidence_url": grant.evidence_url,
        "evidence_path": grant.evidence_path,
        "identity_status": grant.identity_status,
        "target_repo_url": grant.target_repo_url,
    }


def _serialize_commands(trace: AnalysisExecutionTrace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for command in trace.commands:
        rows.append(
            {
                "stage": command.stage,
                "argv": list(command.argv),
                "cwd": command.cwd,
                "started_at": _iso(command.started_at),
                "finished_at": _iso(command.finished_at),
                "exit_code": command.exit_code,
                "isolated_env": command.isolated_env,
            }
        )
    return rows


def _serialize_stages(stages: list[AnalysisStageResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in stages:
        rows.append(
            {
                "stage": stage.stage,
                "outcome": _stage_outcome(stage),
                "success": stage.success,
                "skipped": stage.skipped,
                "summary": stage.summary,
                "started_at": _iso(stage.started_at),
                "finished_at": _iso(stage.finished_at),
                "exit_code": stage.exit_code,
            }
        )
    return rows


def build_analysis_record(
    config: AnalysisConfig,
    result: AnalysisRunResult,
    trace: AnalysisExecutionTrace,
    *,
    archive_path: Path | None = None,
) -> dict[str, Any]:
    grant_path = active_grant_path(_scope_dir_for_config(config))
    identity_stage = next((stage for stage in result.stages if stage.stage == "identity"), None)
    return {
        "schema_version": ANALYSIS_RECORD_SCHEMA_VERSION,
        "record_type": "analysis_run",
        "analysis_id": archive_path.stem if archive_path else None,
        "started_at": _iso(result.started_at),
        "completed_at": _iso(result.completed_at),
        "final_status": derive_final_status(result),
        "target": {
            "target_id": config.target_id,
            "target_ref": config.target_ref,
            "target_commit": result.target_commit,
            "repo_url": config.repo_url or config.grant.target_repo_url,
        },
        "scope_authorization": _serialize_grant_reference(config.grant, grant_path),
        "identity": {
            "identity_status": result.identity_status,
            "verified": identity_stage.success if identity_stage else False,
            "summary": identity_stage.summary if identity_stage else None,
            "blocked_reason": result.blocked_reason,
        },
        "execution_environment": _execution_environment(config, result),
        "tool_versions": _tool_versions(),
        "commands": _serialize_commands(trace),
        "stages": _serialize_stages(result.stages),
        "artifact_paths": {
            "workspace": str(result.workspace.resolve()),
            "active_grant": str(grant_path),
            "confirmation_source": config.grant.confirmation_source,
            "archive_record": str(archive_path) if archive_path else None,
        },
        "error": result.error,
    }
