from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from bugbot.scope import (
    ANALYSIS,
    REVIEWER_DECISION_AUTHORIZED,
    SCOPE_STATUS_NOT_AUTHORIZED,
    ScopeDenialReason,
    ScopeGrant,
    ScopeNotAuthorizedError,
    active_grant_path,
    current_scope_state,
    issue_scope_grant_from_confirmation,
    load_active_grant,
    parse_utc_datetime,
    require_authorized_scope,
    validate_grant_for_request,
    write_active_grant,
)
from bugbot.scope_confirmation import build_scope_grant_from_confirmation


FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID_CONFIRMATION = FIXTURES / "scope_confirmation_valid.md"


def _sample_grant(**overrides) -> ScopeGrant:
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
        "expires_at": datetime(2027, 6, 30, 12, 0, tzinfo=timezone.utc),
        "confirmation_source": str(VALID_CONFIRMATION),
    }
    base.update(overrides)
    return ScopeGrant(**base)


def test_parse_utc_datetime_requires_timezone() -> None:
    assert parse_utc_datetime("2026-06-30T12:00:00+00:00").tzinfo is not None
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_utc_datetime("2026-06-30T12:00:00")


def test_build_scope_grant_from_valid_confirmation(tmp_path: Path) -> None:
    anchor = tmp_path
    evidence = anchor / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    confirmation = anchor / "confirmation.md"
    confirmation.write_text(
        FIXTURES.joinpath("scope_confirmation_valid.md").read_text(encoding="utf-8").replace(
            "tests/fixtures/scope_evidence.md",
            "evidence.md",
        ),
        encoding="utf-8",
    )
    grant, reason = build_scope_grant_from_confirmation(confirmation, anchor_root=anchor)
    assert reason is None
    assert grant is not None
    assert grant.target_id == "dvd-local-lab"
    assert ANALYSIS in grant.permitted_actions


def test_build_scope_grant_rejects_unauthorized_reviewer(tmp_path: Path) -> None:
    anchor = tmp_path
    evidence = anchor / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    confirmation = anchor / "confirmation.md"
    confirmation.write_text(
        FIXTURES.joinpath("scope_confirmation_valid.md")
        .read_text(encoding="utf-8")
        .replace("reviewer_decision: authorized", "reviewer_decision: denied")
        .replace("tests/fixtures/scope_evidence.md", "evidence.md"),
        encoding="utf-8",
    )
    grant, reason = build_scope_grant_from_confirmation(confirmation, anchor_root=anchor)
    assert grant is None
    assert reason is not None
    assert "reviewer_decision" in reason


def test_issue_scope_grant_writes_atomically(tmp_path: Path) -> None:
    anchor = tmp_path
    evidence = anchor / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    confirmation = anchor / "confirmation.md"
    confirmation.write_text(
        FIXTURES.joinpath("scope_confirmation_valid.md").read_text(encoding="utf-8").replace(
            "tests/fixtures/scope_evidence.md",
            "evidence.md",
        ),
        encoding="utf-8",
    )
    scope_dir = anchor / "scope"
    result = issue_scope_grant_from_confirmation(
        confirmation,
        anchor_root=anchor,
        scope_dir=scope_dir,
    )
    assert result.success is True
    assert result.grant_path == active_grant_path(scope_dir)
    grant, reason = load_active_grant(scope_dir)
    assert reason is None
    assert grant is not None
    assert grant.target_id == "dvd-local-lab"


def test_load_active_grant_reports_malformed_json(tmp_path: Path) -> None:
    path = active_grant_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    grant, reason = load_active_grant(tmp_path)
    assert grant is None
    assert ScopeDenialReason.SCOPE_RECORD_MALFORMED in str(reason)


def test_load_active_grant_reports_expired_grant(tmp_path: Path) -> None:
    expired = _sample_grant(
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        evidence_path=str(tmp_path / "evidence.md"),
    )
    (tmp_path / "evidence.md").write_text("evidence", encoding="utf-8")
    write_active_grant(expired, scope_dir=tmp_path)
    grant, reason = load_active_grant(tmp_path)
    assert grant is None
    assert reason == ScopeDenialReason.SCOPE_RECORD_EXPIRED


def test_require_authorized_scope_denies_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANCHOR_ROOT", str(tmp_path))
    with pytest.raises(ScopeNotAuthorizedError) as exc:
        require_authorized_scope(
            target_id="dvd-local-lab",
            target_ref="abc123def4567890abcdef1234567890abcdef12",
            action=ANALYSIS,
        )
    assert exc.value.reason == ScopeDenialReason.NO_SCOPE_GRANT
    assert SCOPE_STATUS_NOT_AUTHORIZED in str(exc.value)


def test_require_authorized_scope_allows_valid_grant(tmp_path: Path) -> None:
    (tmp_path / "evidence.md").write_text("evidence", encoding="utf-8")
    grant = _sample_grant(evidence_path=str(tmp_path / "evidence.md"))
    write_active_grant(grant, scope_dir=tmp_path)
    with patch("bugbot.scope.load_active_grant", lambda scope_dir=None: load_active_grant(tmp_path)):
        returned = require_authorized_scope(
            target_id="dvd-local-lab",
            target_ref="abc123def4567890abcdef1234567890abcdef12",
            action=ANALYSIS,
        )
    assert returned.target_id == "dvd-local-lab"


def test_validate_grant_for_request_rejects_action_not_permitted() -> None:
    grant = _sample_grant(permitted_actions=("planning",))
    assert validate_grant_for_request(
        grant,
        target_id="dvd-local-lab",
        target_ref="abc123def4567890abcdef1234567890abcdef12",
        action=ANALYSIS,
    ) == ScopeDenialReason.ACTION_NOT_PERMITTED


def test_validate_grant_for_request_rejects_target_ref_mismatch() -> None:
    grant = _sample_grant()
    assert validate_grant_for_request(
        grant,
        target_id="dvd-local-lab",
        target_ref="deadbeef",
        action=ANALYSIS,
    ) == ScopeDenialReason.TARGET_REF_MISMATCH


def test_current_scope_state_reflects_active_grant(tmp_path: Path) -> None:
    (tmp_path / "evidence.md").write_text("evidence", encoding="utf-8")
    write_active_grant(_sample_grant(evidence_path=str(tmp_path / "evidence.md")), scope_dir=tmp_path)
    state = current_scope_state(tmp_path)
    assert state.authorized is True
    assert state.target_id == "dvd-local-lab"
