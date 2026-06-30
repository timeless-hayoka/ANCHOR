"""Protected target analysis stages (below scope authorization gate)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from bugbot.scope import (
    IDENTITY_VERIFIED_REPO,
    ScopeGrant,
    default_anchor_root,
)
from bugbot.target_identity import (
    TargetIdentityResult,
    blocked_identity_message,
    verify_target_identity,
)
from knowledge.pipeline import ArchiveResult

logger = logging.getLogger(__name__)

ANALYSIS_STAGES = ("clone", "identity", "inspect", "test", "fuzz")
_SECRET_ENV_MARKERS = ("AWS_", "GITHUB_", "GH_", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_ALLOWED_ENV_PREFIXES = ("PATH", "LANG", "LC_", "FOUNDRY", "RUST", "CARGO")


@dataclass(frozen=True)
class CommandRecord:
    stage: str
    argv: tuple[str, ...]
    cwd: str | None
    started_at: datetime
    finished_at: datetime
    exit_code: int
    isolated_env: bool = False


@dataclass
class AnalysisExecutionTrace:
    commands: list[CommandRecord] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisStageResult:
    stage: str
    success: bool
    summary: str
    skipped: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None


@dataclass(frozen=True)
class AnalysisConfig:
    target_id: str
    target_ref: str
    grant: ScopeGrant
    repo_url: str | None = None
    workspace: Path | None = None
    anchor_root: Path | None = None
    archive: bool = True
    strict_archive: bool = False


@dataclass
class AnalysisRunResult:
    success: bool
    workspace: Path
    stages: list[AnalysisStageResult] = field(default_factory=list)
    error: str | None = None
    blocked: bool = False
    blocked_reason: str | None = None
    identity_status: str | None = None
    trace: AnalysisExecutionTrace = field(default_factory=AnalysisExecutionTrace)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    target_commit: str | None = None
    archive: ArchiveResult | None = None


def default_analysis_workspace(target_id: str, anchor_root: Path | None = None) -> Path:
    root = anchor_root or default_anchor_root()
    safe_id = target_id.replace("/", "_").replace("..", "_")
    return (root / "scope" / "analysis" / safe_id).resolve()


def _head_matches_ref(expected: str, actual: str) -> bool:
    return expected.strip().lower() == actual.strip().lower()


def _run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    trace: AnalysisExecutionTrace | None = None,
    stage: str | None = None,
    isolated_env: bool = False,
) -> subprocess.CompletedProcess[str]:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    finished = datetime.now(timezone.utc)
    if trace is not None and stage:
        trace.commands.append(
            CommandRecord(
                stage=stage,
                argv=tuple(args),
                cwd=str(cwd) if cwd else None,
                started_at=started,
                finished_at=finished,
                exit_code=proc.returncode,
                isolated_env=isolated_env,
            )
        )
    return proc


def _git_head(workspace: Path, trace: AnalysisExecutionTrace | None = None) -> str | None:
    result = _run_command(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        trace=trace,
        stage="clone",
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _effective_repo_url(config: AnalysisConfig) -> str | None:
    return config.repo_url or config.grant.target_repo_url


def _stage_exit_code(trace: AnalysisExecutionTrace, stage: str) -> int | None:
    stage_commands = [command for command in trace.commands if command.stage == stage]
    if not stage_commands:
        return None
    return stage_commands[-1].exit_code


def _stamp_stage(
    result: AnalysisStageResult,
    trace: AnalysisExecutionTrace,
    started: datetime,
    finished: datetime,
) -> AnalysisStageResult:
    return replace(
        result,
        started_at=started,
        finished_at=finished,
        exit_code=_stage_exit_code(trace, result.stage),
    )


def _stage_clone(
    config: AnalysisConfig,
    workspace: Path,
    trace: AnalysisExecutionTrace,
) -> AnalysisStageResult:
    verified = config.grant.identity_status == IDENTITY_VERIFIED_REPO

    if workspace.exists() and any(workspace.iterdir()):
        if (workspace / ".git").is_dir():
            head = _git_head(workspace, trace)
            if head is None:
                return AnalysisStageResult("clone", False, "workspace git repo unreadable")
            return AnalysisStageResult("clone", True, f"using existing workspace at {head[:12]}")
        if verified:
            return AnalysisStageResult(
                "clone",
                False,
                "verified_repo requires a git workspace",
            )
        return AnalysisStageResult(
            "clone",
            True,
            "using existing non-git workspace",
        )

    repo_url = _effective_repo_url(config)
    if not repo_url:
        return AnalysisStageResult(
            "clone",
            False,
            "workspace missing and no repo URL provided",
        )

    workspace.parent.mkdir(parents=True, exist_ok=True)
    clone = _run_command(
        ["git", "clone", "--no-checkout", repo_url, str(workspace)],
        trace=trace,
        stage="clone",
    )
    if clone.returncode != 0:
        detail = (clone.stderr or clone.stdout or "git clone failed").strip()
        return AnalysisStageResult("clone", False, detail)

    checkout_args = ["git", "-C", str(workspace), "checkout"]
    if verified:
        checkout_args.append("--detach")
    checkout_args.append(config.target_ref)
    checkout = _run_command(checkout_args, trace=trace, stage="clone")
    if checkout.returncode != 0:
        detail = (checkout.stderr or checkout.stdout or "git checkout failed").strip()
        return AnalysisStageResult("clone", False, detail)

    head = _git_head(workspace, trace)
    if head is None or (verified and not _head_matches_ref(config.target_ref, head)):
        return AnalysisStageResult("clone", False, "checked out ref does not match target_ref")
    return AnalysisStageResult("clone", True, f"cloned {repo_url} at {head[:12]}")


def _stage_identity(workspace: Path, grant: ScopeGrant) -> tuple[AnalysisStageResult, TargetIdentityResult]:
    identity = verify_target_identity(workspace, grant)
    stage = AnalysisStageResult(
        "identity",
        identity.verified,
        identity.summary,
    )
    return stage, identity


def _count_solidity_files(workspace: Path) -> int:
    return sum(1 for path in workspace.rglob("*.sol") if path.is_file())


def _stage_inspect(workspace: Path) -> AnalysisStageResult:
    if not workspace.is_dir():
        return AnalysisStageResult("inspect", False, f"workspace not found: {workspace}")

    sol_count = _count_solidity_files(workspace)
    has_foundry = (workspace / "foundry.toml").is_file()
    top_level = sorted(item.name for item in workspace.iterdir())[:12]
    summary = (
        f"found {sol_count} Solidity file(s); "
        f"foundry.toml={'yes' if has_foundry else 'no'}; "
        f"entries={', '.join(top_level) if top_level else '(empty)'}"
    )
    if sol_count == 0 and not has_foundry:
        return AnalysisStageResult("inspect", False, summary)
    return AnalysisStageResult("inspect", True, summary)


def _workspace_is_disposable(workspace: Path, anchor_root: Path) -> bool:
    analysis_root = (anchor_root / "scope" / "analysis").resolve()
    try:
        workspace.resolve().relative_to(analysis_root)
        return True
    except ValueError:
        return False


def _isolated_execution_env(workspace: Path) -> dict[str, str]:
    sandbox_home = workspace / ".sandbox-home"
    sandbox_home.mkdir(parents=True, exist_ok=True)
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if any(key == prefix or key.startswith(prefix) for prefix in _ALLOWED_ENV_PREFIXES):
            env[key] = value
    env["HOME"] = str(sandbox_home)
    env["USER"] = "anchor-sandbox"
    for key in list(env):
        upper = key.upper()
        if any(marker in upper for marker in _SECRET_ENV_MARKERS):
            del env[key]
    return env


def _stage_test(
    workspace: Path,
    *,
    grant: ScopeGrant,
    anchor_root: Path,
    trace: AnalysisExecutionTrace,
) -> AnalysisStageResult:
    if grant.identity_status == IDENTITY_VERIFIED_REPO:
        if not _workspace_is_disposable(workspace, anchor_root):
            return AnalysisStageResult(
                "test",
                False,
                "blocked: verified_repo test execution requires disposable workspace under scope/analysis/",
            )

    if shutil.which("forge") is None:
        return AnalysisStageResult("test", True, "skipped: forge not installed", skipped=True)
    if not (workspace / "foundry.toml").is_file():
        return AnalysisStageResult("test", True, "skipped: no foundry.toml", skipped=True)

    isolated = grant.identity_status == IDENTITY_VERIFIED_REPO
    env = _isolated_execution_env(workspace) if isolated else None
    result = _run_command(
        ["forge", "test", "--offline", "-q"],
        cwd=workspace,
        env=env,
        trace=trace,
        stage="test",
        isolated_env=isolated,
    )
    if result.returncode == 0:
        return AnalysisStageResult("test", True, "forge test passed", exit_code=0)
    detail = (result.stderr or result.stdout or "forge test failed").strip()
    lines = [line for line in detail.splitlines() if line.strip()]
    return AnalysisStageResult(
        "test",
        False,
        lines[-1] if lines else "forge test failed",
        exit_code=result.returncode,
    )


def _stage_fuzz(
    workspace: Path,
    *,
    grant: ScopeGrant,
    anchor_root: Path,
) -> AnalysisStageResult:
    if grant.identity_status == IDENTITY_VERIFIED_REPO:
        if not _workspace_is_disposable(workspace, anchor_root):
            return AnalysisStageResult(
                "fuzz",
                False,
                "blocked: verified_repo fuzz execution requires disposable workspace under scope/analysis/",
            )

    if shutil.which("forge") is None:
        return AnalysisStageResult("fuzz", True, "skipped: forge not installed", skipped=True)
    if not (workspace / "foundry.toml").is_file():
        return AnalysisStageResult("fuzz", True, "skipped: no foundry.toml", skipped=True)

    return AnalysisStageResult(
        "fuzz",
        True,
        "skipped: no fuzz profile configured for this target",
        skipped=True,
    )


def _finalize_result(config: AnalysisConfig, result: AnalysisRunResult) -> AnalysisRunResult:
    result.completed_at = datetime.now(timezone.utc)
    if (result.workspace / ".git").is_dir():
        result.target_commit = _git_head(result.workspace, result.trace)
    if not config.archive:
        return result
    from bugbot.analysis_archive import archive_target_analysis

    knowledge_root = (config.anchor_root or default_anchor_root()).resolve() / "knowledge"
    result.archive = archive_target_analysis(
        config,
        result,
        result.trace,
        knowledge_root=knowledge_root,
        strict_archive=config.strict_archive,
    )
    return result


def run_target_analysis(config: AnalysisConfig) -> AnalysisRunResult:
    """
    Execute clone → identity → inspect → test → fuzz for an already authorized target.

    Caller must invoke require_authorized_scope(...) before calling this function.
    """
    anchor_root = (config.anchor_root or default_anchor_root()).resolve()
    workspace = (config.workspace or default_analysis_workspace(config.target_id, anchor_root)).resolve()
    trace = AnalysisExecutionTrace()
    started_at = datetime.now(timezone.utc)
    stages: list[AnalysisStageResult] = []

    stage_started = datetime.now(timezone.utc)
    clone_result = _stage_clone(config, workspace, trace)
    clone_result = _stamp_stage(clone_result, trace, stage_started, datetime.now(timezone.utc))
    stages.append(clone_result)
    logger.info("analysis stage clone: %s", clone_result.summary)
    if not clone_result.success:
        result = AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            error=f"clone failed: {clone_result.summary}",
            trace=trace,
            started_at=started_at,
        )
        return _finalize_result(config, result)

    stage_started = datetime.now(timezone.utc)
    identity_stage, identity = _stage_identity(workspace, config.grant)
    identity_stage = _stamp_stage(identity_stage, trace, stage_started, datetime.now(timezone.utc))
    stages.append(identity_stage)
    logger.info("analysis stage identity: %s", identity.summary)
    if not identity.verified:
        result = AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            blocked=True,
            blocked_reason=identity.blocked_reason,
            identity_status=identity.identity_status,
            error=identity.summary,
            trace=trace,
            started_at=started_at,
        )
        return _finalize_result(config, result)

    stage_started = datetime.now(timezone.utc)
    inspect_result = _stage_inspect(workspace)
    inspect_result = _stamp_stage(inspect_result, trace, stage_started, datetime.now(timezone.utc))
    stages.append(inspect_result)
    logger.info("analysis stage inspect: %s", inspect_result.summary)
    if not inspect_result.success:
        result = AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            identity_status=identity.identity_status,
            error=f"inspect failed: {inspect_result.summary}",
            trace=trace,
            started_at=started_at,
        )
        return _finalize_result(config, result)

    stage_started = datetime.now(timezone.utc)
    test_result = _stage_test(
        workspace,
        grant=config.grant,
        anchor_root=anchor_root,
        trace=trace,
    )
    test_result = _stamp_stage(test_result, trace, stage_started, datetime.now(timezone.utc))
    stages.append(test_result)
    logger.info("analysis stage test: %s", test_result.summary)
    if not test_result.success and not test_result.skipped:
        result = AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            identity_status=identity.identity_status,
            error=f"test failed: {test_result.summary}",
            trace=trace,
            started_at=started_at,
        )
        return _finalize_result(config, result)

    stage_started = datetime.now(timezone.utc)
    fuzz_result = _stage_fuzz(workspace, grant=config.grant, anchor_root=anchor_root)
    fuzz_result = _stamp_stage(fuzz_result, trace, stage_started, datetime.now(timezone.utc))
    stages.append(fuzz_result)
    logger.info("analysis stage fuzz: %s", fuzz_result.summary)
    if not fuzz_result.success and not fuzz_result.skipped:
        result = AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            identity_status=identity.identity_status,
            error=f"fuzz failed: {fuzz_result.summary}",
            trace=trace,
            started_at=started_at,
        )
        return _finalize_result(config, result)

    result = AnalysisRunResult(
        success=True,
        workspace=workspace,
        stages=stages,
        identity_status=identity.identity_status,
        trace=trace,
        started_at=started_at,
    )
    return _finalize_result(config, result)


def render_analysis_report(result: AnalysisRunResult) -> str:
    if result.blocked:
        text = blocked_identity_message(
            TargetIdentityResult(
                verified=False,
                identity_status=result.identity_status or IDENTITY_VERIFIED_REPO,
                summary=result.error or "target identity could not be verified",
                blocked_reason=result.blocked_reason,
            )
        )
        if result.archive and result.archive.success and result.archive.path:
            text += f"\nArchive: {result.archive.path}"
        elif result.archive and not result.archive.success:
            text += f"\nArchive: FAILED — {result.archive.error}"
        return text

    from bugbot.analysis_record import derive_final_status

    lines = [
        f"Analysis: {derive_final_status(result)}",
        f"Workspace: {result.workspace}",
    ]
    if result.identity_status:
        lines.append(f"Identity: {result.identity_status}")
    for stage in result.stages:
        label = stage.stage.upper()
        if stage.skipped:
            state = "SKIP"
        else:
            state = "PASS" if stage.success else "FAIL"
        lines.append(f"{label}: {state} — {stage.summary}")
    if result.error:
        lines.append(f"Error: {result.error}")
    if result.archive and result.archive.success and result.archive.path:
        lines.append(f"Archive: {result.archive.path}")
    elif result.archive and not result.archive.success:
        lines.append(f"Archive: FAILED — {result.archive.error}")
    return "\n".join(lines)
