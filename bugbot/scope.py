"""Authorized-scope gate for BugBot target-touching workflows.

Pipeline stage: crawl → select → plan → scope-check → analysis

Until scope is explicitly authorized, only planning-stage actions are permitted.
Commands that read or execute against selected target code must call
``require_authorized_scope(...)`` as their first line.
"""

from __future__ import annotations

from dataclasses import dataclass

SCOPE_STATUS_NOT_AUTHORIZED = "NOT AUTHORIZED"
ALLOWED_ACTIONS_PLANNING_ONLY = "planning only"

NOT_AUTHORIZED_BANNER = (
    f"Scope status: {SCOPE_STATUS_NOT_AUTHORIZED}\n"
    f"Allowed actions: {ALLOWED_ACTIONS_PLANNING_ONLY}"
)


class ScopeNotAuthorizedError(PermissionError):
    """Raised when a command requires authorized scope but none is recorded."""


@dataclass(frozen=True)
class ScopeState:
    authorized: bool
    target_id: str | None = None
    reason: str | None = None


def current_scope_state() -> ScopeState:
    """Return the active scope authorization state (default: not authorized)."""
    return ScopeState(
        authorized=False,
        target_id=None,
        reason="no scope grant recorded",
    )


def require_authorized_scope(
    *,
    target_id: str | None = None,
    action: str = "target analysis",
) -> None:
    """
    Fail fast unless the selected target is within an authorized scope.

    Call this as the first line of any command that touches selected target code.
    """
    state = current_scope_state()
    if not state.authorized:
        detail = f"Blocked action: {action}"
        if target_id:
            detail = f"{detail}\nTarget: {target_id}"
        raise ScopeNotAuthorizedError(f"{NOT_AUTHORIZED_BANNER}\n{detail}")

    if target_id and state.target_id and target_id != state.target_id:
        raise ScopeNotAuthorizedError(
            f"{NOT_AUTHORIZED_BANNER}\n"
            f"Blocked action: {action}\n"
            f"Target: {target_id}\n"
            f"Authorized target: {state.target_id}"
        )
