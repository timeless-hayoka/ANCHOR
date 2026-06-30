"""Authorized-scope gate for BugBot target-touching workflows.

Pipeline stage: crawl → select → plan → scope-check → analysis

A local grant file may record authorization; it must not invent authorization.
Grants are derived only from validated scope confirmation evidence.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCOPE_STATUS_NOT_AUTHORIZED = "NOT AUTHORIZED"
ALLOWED_ACTIONS_PLANNING_ONLY = "planning only"
REVIEWER_DECISION_AUTHORIZED = "authorized"
ACTIVE_GRANT_FILENAME = "active_grant.json"
GRANT_SCHEMA_VERSION = "1.0"

PLANNING = "planning"
ANALYSIS = "analysis"

IDENTITY_LOCAL_FIXTURE_UNPINNED = "local_fixture_unpinned"
IDENTITY_VERIFIED_REPO = "verified_repo"

NOT_AUTHORIZED_BANNER = (
    f"Scope status: {SCOPE_STATUS_NOT_AUTHORIZED}\n"
    f"Allowed actions: {ALLOWED_ACTIONS_PLANNING_ONLY}"
)


class ScopeDenialReason(StrEnum):
    NO_SCOPE_GRANT = "no scope grant recorded"
    SCOPE_RECORD_MALFORMED = "scope record malformed"
    SCOPE_RECORD_EXPIRED = "scope record expired"
    REVIEWER_NOT_AUTHORIZED = "reviewer not authorized"
    TARGET_MISMATCH = "target mismatch"
    TARGET_REF_MISMATCH = "target ref mismatch"
    ACTION_NOT_PERMITTED = "action not permitted"
    EVIDENCE_MISSING = "evidence reference missing"


class ScopeNotAuthorizedError(PermissionError):
    """Raised when a command requires authorized scope but validation fails."""

    def __init__(self, message: str, *, reason: ScopeDenialReason) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class ScopeGrant:
    schema_version: str
    target_id: str
    target_ref: str
    scope_policy_url: str
    permitted_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    disclosure_channel: str
    evidence_url: str
    evidence_path: str
    reviewer_decision: str
    reviewed_at: datetime
    identity_status: str = IDENTITY_VERIFIED_REPO
    target_repo_url: str | None = None
    expires_at: datetime | None = None
    granted_by: str = "user"
    confirmation_source: str | None = None


@dataclass(frozen=True)
class ScopeState:
    authorized: bool
    target_id: str | None = None
    target_ref: str | None = None
    reason: ScopeDenialReason | str | None = None
    grant: ScopeGrant | None = None


@dataclass(frozen=True)
class ScopeCheckResult:
    success: bool
    grant_path: Path | None = None
    reason: str | None = None


def default_anchor_root() -> Path:
    anchor_root = os.environ.get("ANCHOR_ROOT", "").strip()
    if anchor_root:
        return Path(anchor_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def default_scope_dir() -> Path:
    return (default_anchor_root() / "scope").resolve()


def active_grant_path(scope_dir: Path | None = None) -> Path:
    root = scope_dir or default_scope_dir()
    return root / ACTIVE_GRANT_FILENAME


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize to UTC (timezone required)."""
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _serialize_grant(grant: ScopeGrant) -> dict[str, Any]:
    payload = asdict(grant)
    payload["reviewed_at"] = grant.reviewed_at.isoformat()
    payload["expires_at"] = grant.expires_at.isoformat() if grant.expires_at else None
    payload["permitted_actions"] = list(grant.permitted_actions)
    payload["prohibited_actions"] = list(grant.prohibited_actions)
    return payload


def _deserialize_grant(payload: dict[str, Any]) -> ScopeGrant:
    required = (
        "schema_version",
        "target_id",
        "target_ref",
        "scope_policy_url",
        "permitted_actions",
        "prohibited_actions",
        "disclosure_channel",
        "evidence_url",
        "evidence_path",
        "reviewer_decision",
        "reviewed_at",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")

    expires_raw = payload.get("expires_at")
    return ScopeGrant(
        schema_version=str(payload["schema_version"]),
        target_id=str(payload["target_id"]),
        target_ref=str(payload["target_ref"]),
        scope_policy_url=str(payload["scope_policy_url"]),
        permitted_actions=tuple(str(item) for item in payload["permitted_actions"]),
        prohibited_actions=tuple(str(item) for item in payload["prohibited_actions"]),
        disclosure_channel=str(payload["disclosure_channel"]),
        evidence_url=str(payload["evidence_url"]),
        evidence_path=str(payload["evidence_path"]),
        reviewer_decision=str(payload["reviewer_decision"]).strip().lower(),
        reviewed_at=parse_utc_datetime(str(payload["reviewed_at"])),
        identity_status=str(payload.get("identity_status", IDENTITY_VERIFIED_REPO)).strip(),
        target_repo_url=str(payload["target_repo_url"]).strip()
        if payload.get("target_repo_url")
        else None,
        expires_at=parse_utc_datetime(str(expires_raw)) if expires_raw else None,
        granted_by=str(payload.get("granted_by", "user")),
        confirmation_source=str(payload["confirmation_source"])
        if payload.get("confirmation_source")
        else None,
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def write_active_grant(grant: ScopeGrant, scope_dir: Path | None = None) -> Path:
    path = active_grant_path(scope_dir)
    atomic_write_json(path, _serialize_grant(grant))
    return path


def load_active_grant(scope_dir: Path | None = None) -> tuple[ScopeGrant | None, ScopeDenialReason | str | None]:
    path = active_grant_path(scope_dir)
    if not path.is_file():
        return None, ScopeDenialReason.NO_SCOPE_GRANT

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None, f"{ScopeDenialReason.SCOPE_RECORD_MALFORMED}: grant root must be an object"
        grant = _deserialize_grant(payload)
    except json.JSONDecodeError as exc:
        logger.warning("Active scope grant JSON invalid: %s", exc)
        return None, f"{ScopeDenialReason.SCOPE_RECORD_MALFORMED}: invalid JSON ({exc.msg})"
    except ValueError as exc:
        logger.warning("Active scope grant malformed: %s", exc)
        return None, f"{ScopeDenialReason.SCOPE_RECORD_MALFORMED}: {exc}"
    except TypeError as exc:
        logger.warning("Active scope grant malformed: %s", exc)
        return None, f"{ScopeDenialReason.SCOPE_RECORD_MALFORMED}: {exc}"

    if grant.reviewer_decision != REVIEWER_DECISION_AUTHORIZED:
        return None, ScopeDenialReason.REVIEWER_NOT_AUTHORIZED

    if not Path(grant.evidence_path).is_file():
        return None, ScopeDenialReason.EVIDENCE_MISSING

    now = datetime.now(timezone.utc)
    if grant.expires_at is not None and grant.expires_at <= now:
        return None, ScopeDenialReason.SCOPE_RECORD_EXPIRED

    return grant, None


def validate_grant_for_request(
    grant: ScopeGrant,
    *,
    target_id: str,
    target_ref: str | None,
    action: str,
) -> ScopeDenialReason | None:
    if grant.reviewer_decision != REVIEWER_DECISION_AUTHORIZED:
        return ScopeDenialReason.REVIEWER_NOT_AUTHORIZED
    if grant.target_id != target_id:
        return ScopeDenialReason.TARGET_MISMATCH
    if target_ref is not None and grant.target_ref != target_ref:
        return ScopeDenialReason.TARGET_REF_MISMATCH
    if action not in grant.permitted_actions:
        return ScopeDenialReason.ACTION_NOT_PERMITTED
    if not Path(grant.evidence_path).is_file():
        return ScopeDenialReason.EVIDENCE_MISSING
    if grant.expires_at is not None and grant.expires_at <= datetime.now(timezone.utc):
        return ScopeDenialReason.SCOPE_RECORD_EXPIRED
    return None


def current_scope_state(scope_dir: Path | None = None) -> ScopeState:
    grant, reason = load_active_grant(scope_dir)
    if grant is None:
        return ScopeState(authorized=False, reason=reason)
    return ScopeState(
        authorized=True,
        target_id=grant.target_id,
        target_ref=grant.target_ref,
        grant=grant,
    )


def _deny(
    reason: ScopeDenialReason | str,
    *,
    action: str,
    target_id: str | None = None,
    target_ref: str | None = None,
    grant: ScopeGrant | None = None,
) -> None:
    detail = f"Reason: {reason}\nBlocked action: {action}"
    if target_id:
        detail += f"\nTarget: {target_id}"
    if target_ref:
        detail += f"\nTarget ref: {target_ref}"
    if grant is not None:
        detail += f"\nAuthorized target: {grant.target_id}"
        detail += f"\nAuthorized ref: {grant.target_ref}"
    enum_reason = reason if isinstance(reason, ScopeDenialReason) else ScopeDenialReason.SCOPE_RECORD_MALFORMED
    raise ScopeNotAuthorizedError(f"{NOT_AUTHORIZED_BANNER}\n{detail}", reason=enum_reason)


def require_authorized_scope(
    *,
    target_id: str,
    target_ref: str | None = None,
    action: str = ANALYSIS,
) -> ScopeGrant:
    """
    Fail fast unless the active grant authorizes the requested target and action.

    Call this as the first line of any command that touches selected target code.
    """
    grant, load_reason = load_active_grant()
    if grant is None:
        _deny(load_reason or ScopeDenialReason.NO_SCOPE_GRANT, action=action, target_id=target_id, target_ref=target_ref)

    denial = validate_grant_for_request(
        grant,
        target_id=target_id,
        target_ref=target_ref,
        action=action,
    )
    if denial is not None:
        _deny(denial, action=action, target_id=target_id, target_ref=target_ref, grant=grant)

    return grant


def issue_scope_grant_from_confirmation(
    confirmation_path: Path,
    *,
    anchor_root: Path | None = None,
    scope_dir: Path | None = None,
) -> ScopeCheckResult:
    """Validate scope confirmation evidence and atomically write the active grant."""
    from bugbot.scope_confirmation import build_scope_grant_from_confirmation

    root = anchor_root or default_anchor_root()
    resolved = confirmation_path if confirmation_path.is_absolute() else (root / confirmation_path).resolve()
    if not resolved.is_file():
        return ScopeCheckResult(success=False, reason=f"scope confirmation not found: {resolved}")

    grant, reason = build_scope_grant_from_confirmation(resolved, anchor_root=root)
    if grant is None:
        return ScopeCheckResult(success=False, reason=reason)

    try:
        grant_path = write_active_grant(grant, scope_dir=scope_dir)
    except OSError as exc:
        logger.exception("Failed to write active scope grant")
        return ScopeCheckResult(success=False, reason=f"failed to write active grant: {exc}")

    return ScopeCheckResult(success=True, grant_path=grant_path)
