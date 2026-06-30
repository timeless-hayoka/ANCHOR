"""Protected target analysis stages (below scope authorization gate)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from bugbot.scope import (
    IDENTITY_LOCAL_FIXTURE_UNPINNED,
    IDENTITY_VERIFIED_REPO,
    ScopeGrant,
    default_anchor_root,
)
from bugbot.target_identity import (
    TargetIdentityResult,
    blocked_identity_message,
    verify_target_identity,
)

logger = logging.getLogger(__name__)

ANALYSIS_STAGES = ("clone", "identity", "inspect", "test", "fuzz")
_SECRET_ENV_MARKERS = ("AWS_", "GITHUB_", "GH_", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_ALLOWED_ENV_PREFIXES = ("PATH", "LANG", "LC_", "FOUNDRY", "RUST", "CARGO")


@dataclass(frozen=True)
class AnalysisStageResult:
    stage: str
    success: bool
    summary: str
    skipped: bool = False


@dataclass(frozen=True)
class AnalysisConfig:
    target_id: str
    target_ref: str
    grant: ScopeGrant
    repo_url: str | None = None
    workspace: Path | None = None
    anchor_root: Path | None = None


@dataclass
class AnalysisRunResult:
    success: bool
    workspace: Path
    stages: list[AnalysisStageResult] = field(default_factory=list)
    error: str | None = None
    blocked: bool = False
    blocked_reason: str | None = None
    identity_status: str | None = None


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
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_head(workspace: Path) -> str | None:
    result = _run_command(["git", "-C", str(workspace), "rev-parse", "HEAD"])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _effective_repo_url(config: AnalysisConfig) -> str | None:
    return config.repo_url or config.grant.target_repo_url


def _stage_clone(config: AnalysisConfig, workspace: Path) -> AnalysisStageResult:
    verified = config.grant.identity_status == IDENTITY_VERIFIED_REPO

    if workspace.exists() and any(workspace.iterdir()):
        if (workspace / ".git").is_dir():
            head = _git_head(workspace)
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
    )
    if clone.returncode != 0:
        detail = (clone.stderr or clone.stdout or "git clone failed").strip()
        return AnalysisStageResult("clone", False, detail)

    checkout_args = ["git", "-C", str(workspace), "checkout"]
    if verified:
        checkout_args.append("--detach")
    checkout_args.append(config.target_ref)
    checkout = _run_command(checkout_args)
    if checkout.returncode != 0:
        detail = (checkout.stderr or checkout.stdout or "git checkout failed").strip()
        return AnalysisStageResult("clone", False, detail)

    head = _git_head(workspace)
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

    env = (
        _isolated_execution_env(workspace)
        if grant.identity_status == IDENTITY_VERIFIED_REPO
        else None
    )
    result = _run_command(["forge", "test", "--offline", "-q"], cwd=workspace, env=env)
    if result.returncode == 0:
        return AnalysisStageResult("test", True, "forge test passed")
    detail = (result.stderr or result.stdout or "forge test failed").strip()
    lines = [line for line in detail.splitlines() if line.strip()]
    return AnalysisStageResult("test", False, lines[-1] if lines else "forge test failed")


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


def run_target_analysis(config: AnalysisConfig) -> AnalysisRunResult:
    """
    Execute clone → identity → inspect → test → fuzz for an already authorized target.

    Caller must invoke require_authorized_scope(...) before calling this function.
    """
    anchor_root = (config.anchor_root or default_anchor_root()).resolve()
    workspace = (config.workspace or default_analysis_workspace(config.target_id, anchor_root)).resolve()
    stages: list[AnalysisStageResult] = []

    clone_result = _stage_clone(config, workspace)
    stages.append(clone_result)
    logger.info("analysis stage clone: %s", clone_result.summary)
    if not clone_result.success:
        return AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            error=f"clone failed: {clone_result.summary}",
        )

    identity_stage, identity = _stage_identity(workspace, config.grant)
    stages.append(identity_stage)
    logger.info("analysis stage identity: %s", identity.summary)
    if not identity.verified:
        return AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            blocked=True,
            blocked_reason=identity.blocked_reason,
            identity_status=identity.identity_status,
            error=identity.summary,
        )

    inspect_result = _stage_inspect(workspace)
    stages.append(inspect_result)
    logger.info("analysis stage inspect: %s", inspect_result.summary)
    if not inspect_result.success:
        return AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            identity_status=identity.identity_status,
            error=f"inspect failed: {inspect_result.summary}",
        )

    test_result = _stage_test(workspace, grant=config.grant, anchor_root=anchor_root)
    stages.append(test_result)
    logger.info("analysis stage test: %s", test_result.summary)
    if not test_result.success and not test_result.skipped:
        return AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            identity_status=identity.identity_status,
            error=f"test failed: {test_result.summary}",
        )

    fuzz_result = _stage_fuzz(workspace, grant=config.grant, anchor_root=anchor_root)
    stages.append(fuzz_result)
    logger.info("analysis stage fuzz: %s", fuzz_result.summary)
    if not fuzz_result.success and not fuzz_result.skipped:
        return AnalysisRunResult(
            success=False,
            workspace=workspace,
            stages=stages,
            identity_status=identity.identity_status,
            error=f"fuzz failed: {fuzz_result.summary}",
        )

    return AnalysisRunResult(
        success=True,
        workspace=workspace,
        stages=stages,
        identity_status=identity.identity_status,
    )


def render_analysis_report(result: AnalysisRunResult) -> str:
    if result.blocked:
        return blocked_identity_message(
            TargetIdentityResult(
                verified=False,
                identity_status=result.identity_status or IDENTITY_VERIFIED_REPO,
                summary=result.error or "target identity could not be verified",
                blocked_reason=result.blocked_reason,
            )
        )

    lines = [
        f"Analysis: {'PASS' if result.success else 'FAIL'}",
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
    return "\n".join(lines)
