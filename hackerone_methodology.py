"""Compile reviewed HackerOne scope evidence into a planning-only hunt plan.

This module deliberately does not connect to target assets, create an active
scope grant, or submit reports. It converts a read-only HackerOne snapshot into
a human review worksheet and validates the completed worksheet before selecting
applicable ANCHOR testing methods.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
MAX_REVIEW_LIFETIME = timedelta(days=7)

SYSTEM_KINDS = frozenset({"web", "api", "source", "smart_contract", "mobile", "network"})

METHOD_CATALOG: dict[str, dict[str, Any]] = {
    "passive_recon": {
        "title": "Passive reconnaissance",
        "effect": "read_only",
        "kinds": sorted(SYSTEM_KINDS),
    },
    "manual_http_observation": {
        "title": "Manual HTTP request and response observation",
        "effect": "active",
        "kinds": ["web", "api"],
    },
    "source_review": {
        "title": "Source-code review",
        "effect": "read_only",
        "kinds": ["source", "smart_contract"],
    },
    "dependency_review": {
        "title": "Dependency and supply-chain review",
        "effect": "read_only",
        "kinds": ["source", "web", "api", "mobile", "smart_contract"],
    },
    "web_access_control": {
        "title": "Web access-control and IDOR review",
        "effect": "active",
        "kinds": ["web"],
    },
    "api_authorization": {
        "title": "API object-level authorization review",
        "effect": "active",
        "kinds": ["api"],
    },
    "authentication_session": {
        "title": "Authentication and session review",
        "effect": "active",
        "kinds": ["web", "api", "mobile"],
    },
    "input_validation": {
        "title": "Input-validation review",
        "effect": "active",
        "kinds": ["web", "api", "mobile"],
    },
    "business_logic": {
        "title": "Business-logic review",
        "effect": "active",
        "kinds": ["web", "api", "mobile", "smart_contract"],
    },
    "race_condition": {
        "title": "Race-condition review",
        "effect": "state_changing",
        "kinds": ["web", "api", "smart_contract"],
    },
    "smart_contract_static_analysis": {
        "title": "Smart-contract static analysis",
        "effect": "read_only",
        "kinds": ["smart_contract"],
    },
    "smart_contract_invariant_testing": {
        "title": "Smart-contract invariant testing in an isolated lab",
        "effect": "isolated",
        "kinds": ["smart_contract"],
    },
    "smart_contract_state_diff": {
        "title": "Smart-contract state-difference testing in an isolated lab",
        "effect": "isolated",
        "kinds": ["smart_contract"],
    },
    "smart_contract_oracle_testing": {
        "title": "Oracle edge-case testing in an isolated lab",
        "effect": "isolated",
        "kinds": ["smart_contract"],
    },
    "smart_contract_symbolic_mapping": {
        "title": "Smart-contract symbolic path mapping",
        "effect": "read_only",
        "kinds": ["smart_contract"],
    },
}

# These are never selectable by this compiler, even if a review mistakenly
# lists them as permitted. Program-specific prohibitions can add to this set.
ALWAYS_BLOCKED_METHODS = frozenset(
    {
        "denial_of_service",
        "mass_scanning",
        "social_engineering",
        "credential_stuffing",
        "destructive_testing",
        "access_other_users_data",
        "production_fund_movement",
    }
)


class MethodologyError(ValueError):
    """A safe-to-display methodology validation failure."""


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def payload_sha256(payload: Any) -> str:
    """Return a stable digest for a JSON-compatible payload."""
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _attributes(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("attributes")
    return value if isinstance(value, dict) else {}


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MethodologyError(f"{field} must be a nonempty string")
    return value.strip()


def _parse_timestamp(value: Any, field: str) -> datetime:
    text = _nonempty_string(value, field)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise MethodologyError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise MethodologyError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _string_set(value: Any, field: str) -> set[str]:
    if not isinstance(value, list):
        raise MethodologyError(f"{field} must be a list")
    result: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise MethodologyError(f"{field} entries must be nonempty strings")
        result.add(item.strip())
    return result


def _validate_snapshot(snapshot: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(snapshot, dict):
        raise MethodologyError("snapshot root must be an object")
    handle = _nonempty_string(snapshot.get("program_handle"), "program_handle")
    scopes = snapshot.get("structured_scopes")
    if not isinstance(scopes, list):
        raise MethodologyError("structured_scopes must be a list")
    records = [record for record in scopes if isinstance(record, dict)]
    if not records:
        raise MethodologyError("snapshot has no structured scope records")
    return handle, records


def build_review_template(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Create a fail-closed human review worksheet from a scope snapshot."""
    handle, scopes = _validate_snapshot(snapshot)
    scope_reviews: list[dict[str, Any]] = []
    for record in scopes:
        attributes = _attributes(record)
        scope_id = str(record.get("id", "")).strip()
        if not scope_id:
            continue
        scope_reviews.append(
            {
                "scope_id": scope_id,
                "asset_identifier": attributes.get("asset_identifier"),
                "asset_type": attributes.get("asset_type"),
                "eligible_for_submission": attributes.get("eligible_for_submission") is True,
                "eligible_for_bounty": attributes.get("eligible_for_bounty") is True,
                "instructions": attributes.get("instruction") or attributes.get("instructions"),
                "decision": "pending",
                "system_kinds": [],
                "notes": "",
            }
        )
    if not scope_reviews:
        raise MethodologyError("snapshot has no scope records with stable identifiers")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "hackerone_method_review",
        "program_handle": handle,
        "snapshot_sha256": payload_sha256(snapshot),
        "decision": "pending",
        "reviewer": "",
        "reviewed_at": "",
        "expires_at": "",
        "policy_confirmed": False,
        "exclusions_confirmed": False,
        "active_testing_approved": False,
        "state_changing_approved": False,
        "rate_limit_per_minute": None,
        "permitted_methods": [],
        "prohibited_methods": sorted(ALWAYS_BLOCKED_METHODS),
        "scope_reviews": scope_reviews,
        "notes": "Complete this worksheet from the current program policy. Pending is not authorization.",
    }


def compile_hunt_plan(
    snapshot: dict[str, Any],
    review: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate a completed review and select applicable, approved methods."""
    handle, scopes = _validate_snapshot(snapshot)
    if not isinstance(review, dict):
        raise MethodologyError("review root must be an object")
    if review.get("schema_version") != SCHEMA_VERSION:
        raise MethodologyError("unsupported review schema_version")
    if review.get("artifact_type") != "hackerone_method_review":
        raise MethodologyError("review artifact_type is invalid")
    if review.get("program_handle") != handle:
        raise MethodologyError("review program_handle does not match snapshot")
    if review.get("snapshot_sha256") != payload_sha256(snapshot):
        raise MethodologyError("review does not match the current scope snapshot")
    if review.get("decision") != "approved":
        raise MethodologyError("human review decision must be 'approved'")
    reviewer = _nonempty_string(review.get("reviewer"), "reviewer")
    if review.get("policy_confirmed") is not True:
        raise MethodologyError("policy_confirmed must be true")
    if review.get("exclusions_confirmed") is not True:
        raise MethodologyError("exclusions_confirmed must be true")

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reviewed_at = _parse_timestamp(review.get("reviewed_at"), "reviewed_at")
    expires_at = _parse_timestamp(review.get("expires_at"), "expires_at")
    if reviewed_at > current_time:
        raise MethodologyError("reviewed_at cannot be in the future")
    if expires_at <= current_time:
        raise MethodologyError("review has expired; fetch and review current scope")
    if expires_at - reviewed_at > MAX_REVIEW_LIFETIME:
        raise MethodologyError("review lifetime cannot exceed seven days")

    permitted = _string_set(review.get("permitted_methods"), "permitted_methods")
    prohibited = _string_set(review.get("prohibited_methods"), "prohibited_methods")
    unknown = (permitted | prohibited) - set(METHOD_CATALOG) - ALWAYS_BLOCKED_METHODS
    if unknown:
        raise MethodologyError(f"unknown method identifiers: {', '.join(sorted(unknown))}")
    forbidden_requested = permitted & ALWAYS_BLOCKED_METHODS
    if forbidden_requested:
        raise MethodologyError(
            "always-blocked methods cannot be permitted: " + ", ".join(sorted(forbidden_requested))
        )
    contradictory = permitted & prohibited
    if contradictory:
        raise MethodologyError(
            "methods cannot be both permitted and prohibited: "
            + ", ".join(sorted(contradictory))
        )

    scope_by_id = {str(record.get("id", "")): record for record in scopes}
    scope_reviews = review.get("scope_reviews")
    if not isinstance(scope_reviews, list):
        raise MethodologyError("scope_reviews must be a list")

    selected_scopes: list[dict[str, Any]] = []
    selected_kinds: set[str] = set()
    seen_scope_ids: set[str] = set()
    for entry in scope_reviews:
        if not isinstance(entry, dict):
            raise MethodologyError("scope_reviews entries must be objects")
        scope_id = _nonempty_string(entry.get("scope_id"), "scope_id")
        if scope_id in seen_scope_ids:
            raise MethodologyError(f"duplicate scope review: {scope_id}")
        seen_scope_ids.add(scope_id)
        if scope_id not in scope_by_id:
            raise MethodologyError(f"review references unknown scope: {scope_id}")
        if entry.get("decision") != "in_scope":
            continue
        attributes = _attributes(scope_by_id[scope_id])
        if attributes.get("eligible_for_submission") is not True:
            raise MethodologyError(f"scope {scope_id} is not eligible for submission")
        kinds = _string_set(entry.get("system_kinds"), f"scope {scope_id} system_kinds")
        invalid_kinds = kinds - SYSTEM_KINDS
        if invalid_kinds:
            raise MethodologyError(
                f"scope {scope_id} has unknown system kinds: {', '.join(sorted(invalid_kinds))}"
            )
        if not kinds:
            raise MethodologyError(f"scope {scope_id} requires at least one system kind")
        selected_kinds.update(kinds)
        selected_scopes.append(
            {
                "scope_id": scope_id,
                "asset_identifier": attributes.get("asset_identifier"),
                "asset_type": attributes.get("asset_type"),
                "system_kinds": sorted(kinds),
                "instructions": attributes.get("instruction") or attributes.get("instructions"),
            }
        )
    if not selected_scopes:
        raise MethodologyError("review must mark at least one eligible scope as in_scope")

    rate_limit = review.get("rate_limit_per_minute")
    if not isinstance(rate_limit, int) or isinstance(rate_limit, bool) or rate_limit <= 0:
        raise MethodologyError("rate_limit_per_minute must be a positive integer")

    active_approved = review.get("active_testing_approved") is True
    state_changing_approved = review.get("state_changing_approved") is True
    selected_methods: list[dict[str, Any]] = []
    blocked_methods: list[dict[str, str]] = []
    for method_id in sorted(permitted):
        method = METHOD_CATALOG[method_id]
        if not selected_kinds.intersection(method["kinds"]):
            blocked_methods.append({"method_id": method_id, "reason": "not applicable to selected scopes"})
            continue
        effect = str(method["effect"])
        if effect == "active" and not active_approved:
            blocked_methods.append({"method_id": method_id, "reason": "active testing not approved"})
            continue
        if effect == "state_changing" and not state_changing_approved:
            blocked_methods.append(
                {"method_id": method_id, "reason": "state-changing testing not approved"}
            )
            continue
        selected_methods.append(
            {
                "method_id": method_id,
                "title": method["title"],
                "effect": effect,
            }
        )
    if not selected_methods:
        raise MethodologyError("review permits no applicable methods after safety gates")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "hackerone_hunt_plan",
        "program_handle": handle,
        "compiled_at": current_time.isoformat(),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "snapshot_sha256": payload_sha256(snapshot),
        "review_sha256": payload_sha256(review),
        "authorization_status": "planning_only",
        "execution_authorized": False,
        "scope_recheck_required_before_execution": True,
        "rate_limit_per_minute": rate_limit,
        "selected_scopes": selected_scopes,
        "selected_methods": selected_methods,
        "blocked_methods": blocked_methods,
        "always_blocked_methods": sorted(ALWAYS_BLOCKED_METHODS),
        "promotion_requirements": [
            "Re-fetch scope if the plan is expired or the program policy changes.",
            "Create an ANCHOR active scope grant from reviewed evidence.",
            "Match every action and target to that active grant before execution.",
            "Keep proof minimal, isolated where possible, and stop on unexpected impact.",
        ],
    }


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MethodologyError(f"{label} file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise MethodologyError(f"{label} contains invalid JSON: {exc.msg}") from None
    if not isinstance(payload, dict):
        raise MethodologyError(f"{label} root must be an object")
    return payload


def _write_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-review", help="generate a human review worksheet")
    prepare.add_argument("--snapshot", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    compile_parser = subparsers.add_parser("compile-plan", help="compile an approved review")
    compile_parser.add_argument("--snapshot", type=Path, required=True)
    compile_parser.add_argument("--review", type=Path, required=True)
    compile_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        snapshot = _load_object(args.snapshot, "snapshot")
        if args.command == "prepare-review":
            result = build_review_template(snapshot)
        else:
            review = _load_object(args.review, "review")
            result = compile_hunt_plan(snapshot, review)
        _write_object(args.output, result)
    except MethodologyError as exc:
        print(f"HackerOne methodology failed: {exc}", file=__import__("sys").stderr)
        return 1
    print(f"Wrote {result['artifact_type']} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
