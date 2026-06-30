"""BugBot pedagogical trainer (training logic separate from knowledge archival)."""

from bugbot.scope import (
    ALLOWED_ACTIONS_PLANNING_ONLY,
    ANALYSIS,
    NOT_AUTHORIZED_BANNER,
    PLANNING,
    SCOPE_STATUS_NOT_AUTHORIZED,
    ScopeCheckResult,
    ScopeDenialReason,
    ScopeGrant,
    ScopeNotAuthorizedError,
    ScopeState,
    current_scope_state,
    issue_scope_grant_from_confirmation,
    require_authorized_scope,
)
from bugbot.trainer import BugBotTrainer, TrainingRunResult

__all__ = [
    "ALLOWED_ACTIONS_PLANNING_ONLY",
    "ANALYSIS",
    "BugBotTrainer",
    "NOT_AUTHORIZED_BANNER",
    "PLANNING",
    "SCOPE_STATUS_NOT_AUTHORIZED",
    "ScopeCheckResult",
    "ScopeDenialReason",
    "ScopeGrant",
    "ScopeNotAuthorizedError",
    "ScopeState",
    "TrainingRunResult",
    "current_scope_state",
    "issue_scope_grant_from_confirmation",
    "require_authorized_scope",
]
