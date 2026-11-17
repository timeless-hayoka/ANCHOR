"""Tests for fail-closed HackerOne method planning."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from hackerone_methodology import (
    MethodologyError,
    build_review_template,
    compile_hunt_plan,
    payload_sha256,
)


NOW = datetime(2026, 11, 17, 17, 0, tzinfo=timezone.utc)


def snapshot() -> dict:
    return {
        "schema_version": "1.0",
        "program_handle": "acme",
        "review_required": True,
        "structured_scopes": [
            {
                "id": "web-1",
                "attributes": {
                    "asset_identifier": "https://app.example.test",
                    "asset_type": "URL",
                    "eligible_for_submission": True,
                    "eligible_for_bounty": True,
                    "instruction": "Use the supplied researcher account.",
                },
            },
            {
                "id": "excluded-1",
                "attributes": {
                    "asset_identifier": "legacy.example.test",
                    "asset_type": "DOMAIN",
                    "eligible_for_submission": False,
                },
            },
        ],
        "scope_exclusions": [],
    }


def approved_review() -> tuple[dict, dict]:
    source = snapshot()
    review = build_review_template(source)
    review.update(
        {
            "decision": "approved",
            "reviewer": "human-reviewer",
            "reviewed_at": (NOW - timedelta(hours=1)).isoformat(),
            "expires_at": (NOW + timedelta(days=2)).isoformat(),
            "policy_confirmed": True,
            "exclusions_confirmed": True,
            "active_testing_approved": True,
            "state_changing_approved": False,
            "rate_limit_per_minute": 10,
            "permitted_methods": ["passive_recon", "web_access_control", "race_condition"],
        }
    )
    review["scope_reviews"][0].update(
        {"decision": "in_scope", "system_kinds": ["web"]}
    )
    review["scope_reviews"][1]["decision"] = "out_of_scope"
    return source, review


def test_builds_pending_review_with_scope_evidence_and_no_authorization() -> None:
    review = build_review_template(snapshot())

    assert review["decision"] == "pending"
    assert review["active_testing_approved"] is False
    assert review["state_changing_approved"] is False
    assert review["scope_reviews"][0]["instructions"] == "Use the supplied researcher account."
    assert review["scope_reviews"][1]["eligible_for_submission"] is False
    assert "denial_of_service" in review["prohibited_methods"]


def test_compiles_only_applicable_methods_that_pass_effect_gates() -> None:
    source, review = approved_review()

    plan = compile_hunt_plan(source, review, now=NOW)

    assert plan["authorization_status"] == "planning_only"
    assert plan["execution_authorized"] is False
    assert [item["method_id"] for item in plan["selected_methods"]] == [
        "passive_recon",
        "web_access_control",
    ]
    assert plan["blocked_methods"] == [
        {"method_id": "race_condition", "reason": "state-changing testing not approved"}
    ]
    assert [item["scope_id"] for item in plan["selected_scopes"]] == ["web-1"]


def test_rejects_review_for_changed_snapshot() -> None:
    source, review = approved_review()
    changed = deepcopy(source)
    changed["structured_scopes"][0]["attributes"]["instruction"] = "New rule"

    with pytest.raises(MethodologyError, match="current scope snapshot"):
        compile_hunt_plan(changed, review, now=NOW)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("decision", "pending", "decision"),
        ("policy_confirmed", False, "policy_confirmed"),
        ("exclusions_confirmed", False, "exclusions_confirmed"),
        ("expires_at", (NOW - timedelta(minutes=1)).isoformat(), "expired"),
    ],
)
def test_fails_closed_on_incomplete_or_stale_review(field: str, value: object, message: str) -> None:
    source, review = approved_review()
    review[field] = value

    with pytest.raises(MethodologyError, match=message):
        compile_hunt_plan(source, review, now=NOW)


def test_rejects_ineligible_scope_even_when_reviewer_marks_it_in_scope() -> None:
    source, review = approved_review()
    review["scope_reviews"][1].update(
        {"decision": "in_scope", "system_kinds": ["web"]}
    )

    with pytest.raises(MethodologyError, match="not eligible for submission"):
        compile_hunt_plan(source, review, now=NOW)


@pytest.mark.parametrize("asset_identifier", [None, "   "])
def test_rejects_selected_scope_without_asset_identifier(asset_identifier: object) -> None:
    source, review = approved_review()
    attributes = source["structured_scopes"][0]["attributes"]
    if asset_identifier is None:
        attributes.pop("asset_identifier")
    else:
        attributes["asset_identifier"] = asset_identifier
    review["snapshot_sha256"] = payload_sha256(source)

    with pytest.raises(MethodologyError, match="scope web-1 asset_identifier"):
        compile_hunt_plan(source, review, now=NOW)


def test_normalizes_selected_scope_asset_identifier() -> None:
    source, review = approved_review()
    source["structured_scopes"][0]["attributes"]["asset_identifier"] = (
        "  https://app.example.test  "
    )
    review["snapshot_sha256"] = payload_sha256(source)

    plan = compile_hunt_plan(source, review, now=NOW)

    assert plan["selected_scopes"][0]["asset_identifier"] == "https://app.example.test"


def test_always_blocked_method_cannot_be_permitted() -> None:
    source, review = approved_review()
    review["permitted_methods"].append("denial_of_service")
    review["prohibited_methods"].remove("denial_of_service")

    with pytest.raises(MethodologyError, match="always-blocked"):
        compile_hunt_plan(source, review, now=NOW)


def test_requires_positive_rate_limit() -> None:
    source, review = approved_review()
    review["rate_limit_per_minute"] = 0

    with pytest.raises(MethodologyError, match="positive integer"):
        compile_hunt_plan(source, review, now=NOW)
