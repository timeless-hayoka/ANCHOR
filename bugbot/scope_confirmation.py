"""Parse and validate scope confirmation evidence (markdown or JSON)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bugbot.scope import (
    REVIEWER_DECISION_AUTHORIZED,
    ScopeGrant,
    parse_utc_datetime,
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_REQUIRED_CONFIRMATION_FIELDS = (
    "schema_version",
    "target_id",
    "target_ref",
    "scope_policy_url",
    "permitted_actions",
    "prohibited_actions",
    "disclosure_channel",
    "reviewer_decision",
    "reviewed_at",
    "evidence_url",
    "evidence_path",
)


def _parse_frontmatter_block(text: str) -> dict[str, Any]:
    match = _FRONTMATTER_RE.match(text.strip())
    if not match:
        raise ValueError("scope confirmation markdown missing YAML frontmatter delimiters (---)")

    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, [])
            if not isinstance(data[current_key], list):
                raise ValueError(f"field {current_key} cannot be both scalar and list")
            data[current_key].append(line[4:].strip())
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if not value:
            data[key] = []
        else:
            data[key] = value
    return data


def _coerce_str_list(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        items = tuple(str(item).strip() for item in value if str(item).strip())
        if not items:
            raise ValueError(f"{field} must contain at least one entry")
        return items
    raise ValueError(f"{field} must be a string or list")


def _validate_url(value: str, field: str) -> str:
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an http(s) URL")
    return cleaned


def _normalize_confirmation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in _REQUIRED_CONFIRMATION_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"scope confirmation missing required fields: {', '.join(missing)}")

    reviewer = str(payload["reviewer_decision"]).strip().lower()
    if reviewer != REVIEWER_DECISION_AUTHORIZED:
        raise ValueError(f"reviewer_decision must be {REVIEWER_DECISION_AUTHORIZED!r}")

    reviewed_at = parse_utc_datetime(str(payload["reviewed_at"]))
    expires_raw = payload.get("expires_at")
    expires_at = parse_utc_datetime(str(expires_raw)) if expires_raw not in (None, "") else None

    return {
        "schema_version": str(payload["schema_version"]).strip(),
        "target_id": str(payload["target_id"]).strip(),
        "target_ref": str(payload["target_ref"]).strip(),
        "scope_policy_url": _validate_url(str(payload["scope_policy_url"]), "scope_policy_url"),
        "permitted_actions": _coerce_str_list(payload["permitted_actions"], "permitted_actions"),
        "prohibited_actions": _coerce_str_list(payload["prohibited_actions"], "prohibited_actions"),
        "disclosure_channel": str(payload["disclosure_channel"]).strip(),
        "reviewer_decision": reviewer,
        "reviewed_at": reviewed_at,
        "expires_at": expires_at,
        "evidence_url": _validate_url(str(payload["evidence_url"]), "evidence_url"),
        "evidence_path": str(payload["evidence_path"]).strip(),
        "granted_by": str(payload.get("granted_by", "user")).strip() or "user",
    }


def load_confirmation_payload(path: Path) -> dict[str, Any]:
    """Load structured scope confirmation fields from markdown frontmatter or JSON."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("scope confirmation JSON must be an object")
        return payload
    return _parse_frontmatter_block(text)


def build_scope_grant_from_confirmation(
    confirmation_path: Path,
    *,
    anchor_root: Path,
) -> tuple[ScopeGrant | None, str | None]:
    """
    Derive a ScopeGrant from documented scope evidence.

    Returns (grant, None) on success or (None, specific_reason) on failure.
    """
    try:
        payload = load_confirmation_payload(confirmation_path)
        normalized = _normalize_confirmation_payload(payload)
    except json.JSONDecodeError as exc:
        return None, f"scope record malformed: invalid JSON ({exc.msg})"
    except ValueError as exc:
        return None, f"scope record malformed: {exc}"
    except TypeError as exc:
        return None, f"scope record malformed: {exc}"

    evidence_path = Path(normalized["evidence_path"])
    if not evidence_path.is_absolute():
        evidence_path = (anchor_root / evidence_path).resolve()
    if not evidence_path.is_file():
        return None, f"evidence reference missing: {evidence_path}"

    grant = ScopeGrant(
        schema_version=normalized["schema_version"],
        target_id=normalized["target_id"],
        target_ref=normalized["target_ref"],
        scope_policy_url=normalized["scope_policy_url"],
        permitted_actions=normalized["permitted_actions"],
        prohibited_actions=normalized["prohibited_actions"],
        disclosure_channel=normalized["disclosure_channel"],
        evidence_url=normalized["evidence_url"],
        evidence_path=str(evidence_path),
        reviewer_decision=normalized["reviewer_decision"],
        reviewed_at=normalized["reviewed_at"],
        expires_at=normalized["expires_at"],
        granted_by=normalized["granted_by"],
        confirmation_source=str(confirmation_path.resolve()),
    )
    return grant, None
