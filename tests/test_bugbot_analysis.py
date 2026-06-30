from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bugbot.analysis import (
    AnalysisConfig,
    run_target_analysis,
)


def _init_git_repo(path: Path, message: str = "init") -> str:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    (path / "README.md").write_text("lab", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", message], check=True, capture_output=True, text=True)
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_run_target_analysis_inspects_local_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "lab"
    workspace.mkdir()
    (workspace / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "Token.sol").write_text("// sol", encoding="utf-8")

    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref="deadbeef",
            workspace=workspace,
        )
    )

    assert result.success is True
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["clone"].success is True
    assert "local lab" in stages["clone"].summary
    assert stages["inspect"].success is True
    assert "1 Solidity file" in stages["inspect"].summary
    assert stages["test"].success is True
    assert stages["fuzz"].skipped is True


def test_run_target_analysis_validates_git_ref(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    head = _init_git_repo(workspace)
    (workspace / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "Token.sol").write_text("// sol", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "foundry.toml", "src"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-m", "add lab"], check=True, capture_output=True)
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    bad = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref="0000000000000000000000000000000000000000",
            workspace=workspace,
        )
    )
    assert bad.success is False
    assert bad.error is not None
    assert "clone failed" in bad.error

    good = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref=head,
            workspace=workspace,
        )
    )
    assert good.success is True


def test_run_target_analysis_requires_repo_url_for_missing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "missing"
    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref="abc123",
            workspace=workspace,
        )
    )
    assert result.success is False
    assert result.stages[0].stage == "clone"
    assert "no --repo-url" in result.stages[0].summary
