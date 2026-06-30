"""BugBot pedagogical trainer (training logic separate from knowledge archival)."""

from bugbot.scope import (
    ALLOWED_ACTIONS_PLANNING_ONLY,
    NOT_AUTHORIZED_BANNER,
    SCOPE_STATUS_NOT_AUTHORIZED,
    ScopeNotAuthorizedError,
    ScopeState,
    current_scope_state,
    require_authorized_scope,
)
from bugbot.trainer import BugBotTrainer, TrainingRunResult

__all__ = [
    "ALLOWED_ACTIONS_PLANNING_ONLY",
    "BugBotTrainer",
    "NOT_AUTHORIZED_BANNER",
    "SCOPE_STATUS_NOT_AUTHORIZED",
    "ScopeNotAuthorizedError",
    "ScopeState",
    "TrainingRunResult",
    "current_scope_state",
    "require_authorized_scope",
]
