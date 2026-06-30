"""Protected target analysis stages (below scope authorization gate)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from bugbot.scope import default_anchor_root

logger = logging.getLogger(__name__)

ANALYSIS_STAGES = ("clone", "inspect", "test", "fuzz")


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
    repo_url: str | None = None
    workspace: Path | None = None


@dataclass
class AnalysisRunResult:
    success: bool
    workspace: Path
    stages: list[AnalysisStageResult] = field(default_factory=list)
    error: str | None = None


def default_analysis_workspace(target_id: str, anchor_root: Path | None = None) -> Path:
    root = anchor_root or default_anchor_root()
    safe_id = target_id.replace("/", "_").replace("..", "_")
    return (root / "scope" / "analysis" / safe_id).resolve()


def _refs_match(expected: str, actual: str) -> bool:
    expected_norm = expected.strip().lower()
    actual_norm = actual.strip().lower()
    if not expected_norm or not actual_norm:
        return False
    if expected_norm == actual_norm:
        return True
    shorter, longer = sorted((expected_norm, actual_norm), key=len)
    return longer.startswith(shorter)


def _run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_head(workspace: Path) -> str | None:
    result = _run_command(["git", "-C", str(workspace), "rev-parse", "HEAD"])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _stage_clone(config: AnalysisConfig, workspace: Path) -> AnalysisStageResult:
    if workspace.exists() and any(workspace.iterdir()):
        if (workspace / ".git").is_dir():
            head = _git_head(workspace)
            if head is None:
                return AnalysisStageResult("clone", False, "workspace git repo unreadable")
            if not _refs_match(config.target_ref, head):
                return AnalysisStageResult(
                    "clone",
                    False,
                    f"workspace ref mismatch: expected {config.target_ref}, found {head}",
                )
            return AnalysisStageResult("clone", True, f"using existing workspace at {head[:12]}")
        return AnalysisStageResult(
            "clone",
            True,
            "using existing non-git workspace (local lab target)",
        )

    if not config.repo_url:
        return AnalysisStageResult(
            "clone",
            False,
            "workspace missing and no --repo-url provided",
        )

    workspace.parent.mkdir(parents=True, exist_ok=True)
    clone = _run_command(
        ["git", "clone", "--no-checkout", config.repo_url, str(workspace)],
    )
    if clone.returncode != 0:
        detail = (clone.stderr or clone.stdout or "git clone failed").strip()
        return AnalysisStageResult("clone", False, detail)

    checkout = _run_command(["git", "-C", str(workspace), "checkout", config.target_ref])
    if checkout.returncode != 0:
        detail = (checkout.stderr or checkout.stdout or "git checkout failed").strip()
        return AnalysisStageResult("clone", False, detail)

    head = _git_head(workspace)
    if head is None or not _refs_match(config.target_ref, head):
        return AnalysisStageResult("clone", False, "checked out ref does not match target_ref")
    return AnalysisStageResult("clone", True, f"cloned {config.repo_url} at {head[:12]}")


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


def _stage_test(workspace: Path) -> AnalysisStageResult:
    if shutil.which("forge") is None:
        return AnalysisStageResult("test", True, "skipped: forge not installed", skipped=True)
    if not (workspace / "foundry.toml").is_file():
        return AnalysisStageResult("test", True, "skipped: no foundry.toml", skipped=True)

    result = _run_command(["forge", "test", "--offline", "-q"], cwd=workspace)
    if result.returncode == 0:
        return AnalysisStageResult("test", True, "forge test passed")
    detail = (result.stderr or result.stdout or "forge test failed").strip()
    lines = [line for line in detail.splitlines() if line.strip()]
    return AnalysisStageResult("test", False, lines[-1] if lines else "forge test failed")


def _stage_fuzz(workspace: Path) -> AnalysisStageResult:
    if shutil.which("forge") is None:
        return AnalysisStageResult("fuzz", True, "skipped: forge not installed", skipped=True)
    if not (workspace / "foundry.toml").is_file():
        return AnalysisStageResult("fuzz", True, "skipped: no foundry.toml", skipped=True)

    # Minimal placeholder: real fuzz campaigns are configured per-target later.
    return AnalysisStageResult(
        "fuzz",
        True,
        "skipped: no fuzz profile configured for this target",
        skipped=True,
    )


def run_target_analysis(config: AnalysisConfig) -> AnalysisRunResult:
    """
    Execute clone → inspect → test → fuzz for an already authorized target.

    Caller must invoke require_authorized_scope(...) before calling this function.
    """
    workspace = (config.workspace or default_analysis_workspace(config.target_id)).resolve()
    stages: list[AnalysisStageResult] = []

    for stage_name, runner in (
        ("clone", lambda: _stage_clone(config, workspace)),
        ("inspect", lambda: _stage_inspect(workspace)),
        ("test", lambda: _stage_test(workspace)),
        ("fuzz", lambda: _stage_fuzz(workspace)),
    ):
        result = runner()
        stages.append(result)
        logger.info("analysis stage %s: %s", stage_name, result.summary)
        if not result.success and not result.skipped:
            return AnalysisRunResult(
                success=False,
                workspace=workspace,
                stages=stages,
                error=f"{stage_name} failed: {result.summary}",
            )

    return AnalysisRunResult(success=True, workspace=workspace, stages=stages)


def render_analysis_report(result: AnalysisRunResult) -> str:
    lines = [
        f"Analysis: {'PASS' if result.success else 'FAIL'}",
        f"Workspace: {result.workspace}",
    ]
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
