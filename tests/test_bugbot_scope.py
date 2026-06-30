from __future__ import annotations

import pytest

from bugbot.scope import (
    ALLOWED_ACTIONS_PLANNING_ONLY,
    NOT_AUTHORIZED_BANNER,
    SCOPE_STATUS_NOT_AUTHORIZED,
    ScopeNotAuthorizedError,
    ScopeState,
    current_scope_state,
    require_authorized_scope,
)


def test_current_scope_state_defaults_to_not_authorized() -> None:
    state = current_scope_state()
    assert state.authorized is False
    assert state.target_id is None
    assert state.reason == "no scope grant recorded"


def test_require_authorized_scope_raises_by_default() -> None:
    with pytest.raises(ScopeNotAuthorizedError) as exc:
        require_authorized_scope(target_id="uups_initializer_takeover", action="analysis")

    message = str(exc.value)
    assert SCOPE_STATUS_NOT_AUTHORIZED in message
    assert ALLOWED_ACTIONS_PLANNING_ONLY in message
    assert "Blocked action: analysis" in message
    assert "Target: uups_initializer_takeover" in message
    assert message.startswith(NOT_AUTHORIZED_BANNER.splitlines()[0])


def test_require_authorized_scope_passes_when_authorized(monkeypatch) -> None:
    monkeypatch.setattr(
        "bugbot.scope.current_scope_state",
        lambda: ScopeState(authorized=True, target_id="uups_initializer_takeover"),
    )
    require_authorized_scope(
        target_id="uups_initializer_takeover",
        action="analysis",
    )


def test_require_authorized_scope_rejects_mismatched_target(monkeypatch) -> None:
    monkeypatch.setattr(
        "bugbot.scope.current_scope_state",
        lambda: ScopeState(authorized=True, target_id="other-target"),
    )
    with pytest.raises(ScopeNotAuthorizedError) as exc:
        require_authorized_scope(target_id="uups_initializer_takeover", action="analysis")
    assert "Authorized target: other-target" in str(exc.value)
