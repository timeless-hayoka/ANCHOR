from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bugbot.analysis import (
    AnalysisConfig,
    render_analysis_report,
    run_target_analysis,
)
from bugbot.scope import (
    ANALYSIS,
    IDENTITY_LOCAL_FIXTURE_UNPINNED,
    IDENTITY_VERIFIED_REPO,
    REVIEWER_DECISION_AUTHORIZED,
    ScopeGrant,
)
from bugbot.target_identity import normalize_git_remote

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _local_fixture_grant(**overrides) -> ScopeGrant:
    base = {
        "schema_version": "1.0",
        "target_id": "dvd-local-lab",
        "target_ref": "abc123def4567890abcdef1234567890abcdef12",
        "scope_policy_url": "https://example.com/security/scope",
        "permitted_actions": (ANALYSIS,),
        "prohibited_actions": ("mainnet-exploit",),
        "disclosure_channel": "local-lab-only",
        "evidence_url": "https://example.com/evidence/dvd-local-lab",
        "evidence_path": str(FIXTURES / "scope_evidence.md"),
        "reviewer_decision": REVIEWER_DECISION_AUTHORIZED,
        "reviewed_at": datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
        "identity_status": IDENTITY_LOCAL_FIXTURE_UNPINNED,
        "expires_at": datetime(2027, 6, 30, 12, 0, tzinfo=timezone.utc),
        "confirmation_source": str(FIXTURES / "scope_confirmation_valid.md"),
    }
    base.update(overrides)
    return ScopeGrant(**base)


def _verified_grant(target_ref: str, repo_url: str, **overrides) -> ScopeGrant:
    return _local_fixture_grant(
        identity_status=IDENTITY_VERIFIED_REPO,
        target_ref=target_ref,
        target_repo_url=repo_url,
        **overrides,
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


def test_normalize_git_remote_matches_ssh_and_https() -> None:
    assert normalize_git_remote("https://github.com/org/repo.git") == normalize_git_remote(
        "git@github.com:org/repo"
    )


def test_run_target_analysis_inspects_local_fixture_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "lab"
    workspace.mkdir()
    (workspace / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "Token.sol").write_text("// sol", encoding="utf-8")

    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref="deadbeef",
            grant=_local_fixture_grant(),
            workspace=workspace,
            anchor_root=tmp_path,
        )
    )

    assert result.success is True
    assert result.identity_status == IDENTITY_LOCAL_FIXTURE_UNPINNED
    assert result.archive is not None and result.archive.success is True
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["clone"].success is True
    assert stages["identity"].success is True
    assert "local_fixture_unpinned" in stages["identity"].summary
    assert stages["inspect"].success is True
    assert "1 Solidity file" in stages["inspect"].summary
    assert stages["test"].success is True
    assert stages["fuzz"].skipped is True


def test_verified_repo_blocks_wrong_head(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    head = _init_git_repo(workspace)
    subprocess.run(
        ["git", "-C", str(workspace), "remote", "add", "origin", "https://github.com/example/lab.git"],
        check=True,
        capture_output=True,
    )

    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref=head,
            grant=_verified_grant(
                "0000000000000000000000000000000000000000",
                "https://github.com/example/lab.git",
            ),
            workspace=workspace,
            anchor_root=tmp_path,
        )
    )

    assert result.success is False
    assert result.blocked is True
    assert "Analysis: BLOCKED" in render_analysis_report(result)
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["identity"].success is False
    assert "does not exactly match" in stages["identity"].summary


def test_verified_repo_passes_with_matching_origin_and_head(tmp_path: Path) -> None:
    anchor = tmp_path / "anchor"
    workspace = anchor / "scope" / "analysis" / "dvd-local-lab"
    workspace.mkdir(parents=True)
    head = _init_git_repo(workspace)
    (workspace / "src").mkdir()
    (workspace / "src" / "Token.sol").write_text("// sol", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "src"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-m", "add lab"], check=True, capture_output=True)
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(workspace), "remote", "add", "origin", "https://github.com/example/lab.git"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(workspace), "checkout", "--detach", head], check=True, capture_output=True)

    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref=head,
            grant=_verified_grant(head, "https://github.com/example/lab.git"),
            workspace=workspace,
            anchor_root=anchor,
        )
    )

    assert result.success is True
    assert result.identity_status == IDENTITY_VERIFIED_REPO
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["identity"].success is True


def test_verified_repo_blocks_test_outside_disposable_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "outside" / "repo"
    workspace.mkdir(parents=True)
    head = _init_git_repo(workspace)
    (workspace / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(workspace), "remote", "add", "origin", "https://github.com/example/lab.git"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(workspace), "checkout", "--detach", head], check=True, capture_output=True)

    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref=head,
            grant=_verified_grant(head, "https://github.com/example/lab.git"),
            workspace=workspace,
            anchor_root=tmp_path / "anchor",
        )
    )

    assert result.success is False
    stages = {stage.stage: stage for stage in result.stages}
    assert stages["identity"].success is True
    assert stages["test"].success is False
    assert "disposable workspace" in stages["test"].summary


def test_run_target_analysis_requires_repo_url_for_missing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "missing"
    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref="abc123",
            grant=_local_fixture_grant(),
            workspace=workspace,
            anchor_root=tmp_path,
        )
    )
    assert result.success is False
    assert result.stages[0].stage == "clone"
    assert "no repo URL" in result.stages[0].summary
