from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bugbot.scope import (
    ANALYSIS,
    IDENTITY_LOCAL_FIXTURE_UNPINNED,
    IDENTITY_VERIFIED_REPO,
    REVIEWER_DECISION_AUTHORIZED,
    ScopeGrant,
)
from bugbot.target_identity import (
    blocked_identity_message,
    normalize_git_remote,
    verify_target_identity,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _grant(**overrides) -> ScopeGrant:
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


def test_local_fixture_unpinned_allows_non_git_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "fixture"
    workspace.mkdir()
    result = verify_target_identity(workspace, _grant())
    assert result.verified is True
    assert result.identity_status == IDENTITY_LOCAL_FIXTURE_UNPINNED
    assert "unpinned" in result.summary


def test_verified_repo_requires_git_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "fixture"
    workspace.mkdir()
    result = verify_target_identity(
        workspace,
        _grant(
            identity_status=IDENTITY_VERIFIED_REPO,
            target_repo_url="https://github.com/example/lab.git",
        ),
    )
    assert result.verified is False
    assert "not a git repository" in result.summary


def test_blocked_message_is_explicit() -> None:
    message = blocked_identity_message(
        verify_target_identity(
            Path("/tmp/missing"),
            _grant(
                identity_status=IDENTITY_VERIFIED_REPO,
                target_repo_url="https://github.com/example/lab.git",
            ),
        )
    )
    assert "Analysis: BLOCKED" in message
    assert "target identity could not be verified" in message
    assert "scope review and planning only" in message


def test_normalize_git_remote_strips_suffix() -> None:
    assert normalize_git_remote("HTTPS://GitHub.com/Org/Repo.git") == "github.com/org/repo"
