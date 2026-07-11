from __future__ import annotations

import json
from pathlib import Path

import pytest

from trinity_lead_state_machine import (
    ALLOWED_TRANSITIONS,
    LEAD_STATES,
    SCHEMA_VERSION,
    STATES_REQUIRING_EVIDENCE,
    STATES_REQUIRING_REVIEW,
    TERMINAL_STATES,
    LeadEvent,
    LeadRecord,
    LeadTransitionError,
    apply_transition,
    can_transition,
    render_lead_state,
    utcnow_iso,
    validate_lead,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _new_lead() -> LeadRecord:
    return LeadRecord(lead_id="lead_x", target="authorized-demo-target", title="Test lead")


def test_signal_lead_is_valid_with_no_rubric_fields():
    record = _new_lead()
    assert record.state == "signal"
    assert validate_lead(record) == []


def test_can_transition_matches_canonical_graph():
    assert can_transition("signal", "hypothesis")
    assert can_transition("council_accepted", "report_ready")
    assert not can_transition("signal", "report_ready")
    assert not can_transition("report_ready", "rejected")


def test_apply_transition_rejects_illegal_jump():
    record = _new_lead()
    with pytest.raises(LeadTransitionError, match="illegal transition"):
        apply_transition(record, to_state="report_ready", actor="trinity", reason="skip ahead", event_id="evt_1")


def test_apply_transition_rejects_missing_required_fields():
    record = _new_lead()
    with pytest.raises(LeadTransitionError, match="claim"):
        apply_transition(record, to_state="hypothesis", actor="trinity", reason="no fields set", event_id="evt_1")


def _promote_to_hypothesis(record: LeadRecord) -> LeadRecord:
    record.claim = "claim"
    record.scope = "scope"
    record.mechanism = "mechanism"
    record.falsifier = "falsifier"
    return apply_transition(record, to_state="hypothesis", actor="trinity", reason="promote", event_id="evt_1")


def test_promotion_to_report_ready_requires_reproduction_and_impact_evidence():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")

    with pytest.raises(LeadTransitionError, match="evidence_refs"):
        apply_transition(record, to_state="reproduced_real", actor="evidence-gate", reason="no evidence yet", event_id="evt_3")

    record = apply_transition(
        record,
        to_state="reproduced_real",
        actor="evidence-gate",
        reason="repro demonstrated",
        event_id="evt_3",
        evidence_refs=["evidence/forge_output.txt"],
    )

    with pytest.raises(LeadTransitionError, match="impact_boundary"):
        apply_transition(record, to_state="council_accepted", actor="council", reason="no impact yet", event_id="evt_4")

    record.impact_boundary = "impact boundary"
    with pytest.raises(LeadTransitionError, match="review_refs"):
        apply_transition(record, to_state="council_accepted", actor="council", reason="no review yet", event_id="evt_4")

    record.review_refs = ["reviews/council_review.md"]
    record = apply_transition(record, to_state="council_accepted", actor="council", reason="accepted", event_id="evt_4")

    record = apply_transition(record, to_state="report_ready", actor="anchor", reason="archived", event_id="evt_5")
    assert record.state == "report_ready"
    assert validate_lead(record) == []
    assert len(record.events) == 5


def test_terminal_states_have_no_outgoing_transitions():
    for terminal in ("report_ready", "rejected", "out_of_scope", "duplicate"):
        assert can_transition(terminal, "signal") is False


def test_round_trip_to_dict_from_dict():
    record = _promote_to_hypothesis(_new_lead())
    payload = record.to_dict()
    restored = LeadRecord.from_dict(payload)
    assert restored.to_dict() == payload


def test_render_lead_state_flags_invalid_records():
    record = _new_lead()
    record.state = "hypothesis"  # required fields not set
    line = render_lead_state(record)
    assert "INVALID" in line
    assert "lead_x" in line


def test_example_file_is_valid_and_report_ready(tmp_path=None):
    from pathlib import Path

    example_path = Path(__file__).resolve().parent.parent / "examples" / "trinity_lead_state_machine.example.json"
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    record = LeadRecord.from_dict(payload)
    assert record.state == "report_ready"
    assert validate_lead(record) == []


# --- transition graph edge cases -------------------------------------------------


def test_can_transition_returns_false_for_unknown_from_state():
    assert can_transition("not_a_real_state", "signal") is False


def test_needs_environment_round_trip_back_to_repro_attempted():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")

    record = apply_transition(
        record, to_state="needs_environment", actor="forge", reason="fork unavailable", event_id="evt_3"
    )
    assert record.state == "needs_environment"
    assert validate_lead(record) == []

    record = apply_transition(
        record, to_state="repro_attempted", actor="forge", reason="fork restored", event_id="evt_4"
    )
    assert record.state == "repro_attempted"
    assert validate_lead(record) == []


def test_needs_environment_can_be_rejected():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")
    record = apply_transition(
        record, to_state="needs_environment", actor="forge", reason="fork unavailable", event_id="evt_3"
    )
    record = apply_transition(record, to_state="rejected", actor="trinity", reason="abandoned", event_id="evt_4")
    assert record.state == "rejected"
    assert validate_lead(record) == []


def test_hypothesis_to_needs_manual_review_requires_repro_plan():
    record = _promote_to_hypothesis(_new_lead())
    assert record.repro_plan == ""

    with pytest.raises(LeadTransitionError, match="repro_plan"):
        apply_transition(
            record, to_state="needs_manual_review", actor="reviewer", reason="needs a look", event_id="evt_2"
        )

    record.repro_plan = "repro plan"
    record = apply_transition(
        record, to_state="needs_manual_review", actor="reviewer", reason="needs a look", event_id="evt_2"
    )
    assert record.state == "needs_manual_review"
    # needs_manual_review does not currently require evidence_refs/review_refs.
    assert validate_lead(record) == []


def test_needs_manual_review_can_fall_back_to_hypothesis():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(
        record, to_state="needs_manual_review", actor="reviewer", reason="needs a look", event_id="evt_2"
    )

    fallback = apply_transition(
        record, to_state="hypothesis", actor="reviewer", reason="send back for more work", event_id="evt_3"
    )
    assert fallback.state == "hypothesis"
    assert validate_lead(fallback) == []


def test_needs_manual_review_can_advance_to_council_accepted():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")
    record = apply_transition(
        record,
        to_state="reproduced_real",
        actor="evidence-gate",
        reason="repro demonstrated",
        event_id="evt_3",
        evidence_refs=["evidence/forge_output.txt"],
    )
    record = apply_transition(
        record, to_state="needs_manual_review", actor="reviewer", reason="double check", event_id="evt_4"
    )

    record.impact_boundary = "impact boundary"
    record.review_refs = ["reviews/council_review.md"]
    record = apply_transition(record, to_state="council_accepted", actor="council", reason="accepted", event_id="evt_5")
    assert record.state == "council_accepted"
    assert validate_lead(record) == []


def test_kill_transitions_do_not_require_rubric_fields():
    for to_state in ("rejected", "out_of_scope", "duplicate"):
        record = _new_lead()
        killed = apply_transition(record, to_state=to_state, actor="trinity", reason="killed", event_id="evt_k")
        assert killed.state == to_state
        assert validate_lead(killed) == []


def test_terminal_states_constant_matches_expected_set():
    assert TERMINAL_STATES == frozenset({"report_ready", "rejected", "out_of_scope", "duplicate"})
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_allowed_transitions_has_entry_for_every_lead_state():
    assert set(ALLOWED_TRANSITIONS.keys()) == set(LEAD_STATES)


# --- validate_lead direct checks -------------------------------------------------


def test_validate_lead_short_circuits_on_unknown_state():
    record = _new_lead()
    record.state = "not_a_real_state"
    assert validate_lead(record) == ["unknown state 'not_a_real_state'"]


def test_validate_lead_reports_unknown_scope_status():
    record = _new_lead()
    record.scope_status = "not_a_real_status"
    errors = validate_lead(record)
    assert "unknown scope_status 'not_a_real_status'" in errors


def test_validate_lead_reports_missing_identity_fields():
    record = LeadRecord(lead_id="", target="", title="")
    errors = validate_lead(record)
    assert "lead_id is required" in errors
    assert "target is required" in errors
    assert "title is required" in errors


# --- apply_transition mechanics --------------------------------------------------


def test_apply_transition_rejects_unknown_target_state():
    record = _new_lead()
    with pytest.raises(LeadTransitionError, match="unknown target state"):
        apply_transition(record, to_state="not_a_real_state", actor="trinity", reason="bogus", event_id="evt_1")


def test_apply_transition_deduplicates_evidence_refs_against_existing_entries():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"

    record = apply_transition(
        record,
        to_state="repro_attempted",
        actor="forge",
        reason="attempt",
        event_id="evt_2",
        evidence_refs=["evidence/a.txt"],
    )
    assert record.evidence_refs == ["evidence/a.txt"]

    record = apply_transition(
        record,
        to_state="reproduced_real",
        actor="evidence-gate",
        reason="repro demonstrated",
        event_id="evt_3",
        evidence_refs=["evidence/a.txt", "evidence/b.txt"],
    )
    # "evidence/a.txt" was already recorded, so only "evidence/b.txt" is appended.
    assert record.evidence_refs == ["evidence/a.txt", "evidence/b.txt"]


def test_apply_transition_preserves_duplicate_refs_within_a_single_call():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"

    record = apply_transition(
        record,
        to_state="repro_attempted",
        actor="forge",
        reason="attempt",
        event_id="evt_2",
        evidence_refs=["evidence/dup.txt", "evidence/dup.txt"],
    )
    # Dedup only guards against refs already present on the record; repeats
    # supplied within the same call are not collapsed.
    assert record.evidence_refs == ["evidence/dup.txt", "evidence/dup.txt"]


def test_apply_transition_sets_created_at_once_and_updates_updated_at():
    record = _new_lead()
    assert record.created_at == ""
    record.claim = "claim"
    record.scope = "scope"
    record.mechanism = "mechanism"
    record.falsifier = "falsifier"

    record = apply_transition(
        record,
        to_state="hypothesis",
        actor="trinity",
        reason="promote",
        event_id="evt_1",
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert record.created_at == "2026-01-01T00:00:00+00:00"
    assert record.updated_at == "2026-01-01T00:00:00+00:00"

    record.repro_plan = "repro plan"
    record = apply_transition(
        record,
        to_state="repro_attempted",
        actor="forge",
        reason="attempt",
        event_id="evt_2",
        created_at="2026-01-02T00:00:00+00:00",
    )
    # created_at is preserved from the first transition; only updated_at advances.
    assert record.created_at == "2026-01-01T00:00:00+00:00"
    assert record.updated_at == "2026-01-02T00:00:00+00:00"


def test_apply_transition_uses_utcnow_iso_when_created_at_not_supplied(monkeypatch):
    import trinity_lead_state_machine as tlsm

    monkeypatch.setattr(tlsm, "utcnow_iso", lambda: "2026-05-05T05:05:05+00:00")

    record = _new_lead()
    record.claim = "claim"
    record.scope = "scope"
    record.mechanism = "mechanism"
    record.falsifier = "falsifier"

    record = tlsm.apply_transition(record, to_state="hypothesis", actor="trinity", reason="promote", event_id="evt_1")
    assert record.created_at == "2026-05-05T05:05:05+00:00"
    assert record.updated_at == "2026-05-05T05:05:05+00:00"


def test_apply_transition_records_from_state_and_actor_on_event():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")

    last_event = record.events[-1]
    assert last_event.event_id == "evt_2"
    assert last_event.from_state == "hypothesis"
    assert last_event.to_state == "repro_attempted"
    assert last_event.actor == "forge"
    assert last_event.reason == "attempt"


# --- LeadEvent / LeadRecord serialization ----------------------------------------


def test_lead_event_to_dict_and_from_dict_round_trip():
    event = LeadEvent(
        event_id="evt_1",
        lead_id="lead_x",
        from_state="signal",
        to_state="hypothesis",
        actor="trinity",
        reason="promote",
        evidence_refs=("a.txt", "b.txt"),
        created_at="2026-01-01T00:00:00+00:00",
    )
    payload = event.to_dict()
    assert payload == {
        "event_id": "evt_1",
        "lead_id": "lead_x",
        "from_state": "signal",
        "to_state": "hypothesis",
        "actor": "trinity",
        "reason": "promote",
        "evidence_refs": ["a.txt", "b.txt"],
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    restored = LeadEvent.from_dict(payload)
    assert restored == event


def test_lead_record_from_dict_defaults_for_missing_optional_fields():
    record = LeadRecord.from_dict({"lead_id": "lead_x", "target": "t", "title": "Title"})
    assert record.state == "signal"
    assert record.scope_status == "unknown"
    assert record.claim == ""
    assert record.impact_boundary == ""
    assert record.evidence_refs == []
    assert record.review_refs == []
    assert record.events == []
    assert record.created_at == ""
    assert record.updated_at == ""


def test_lead_record_from_dict_ignores_non_list_refs_and_events():
    record = LeadRecord.from_dict(
        {
            "lead_id": "lead_x",
            "target": "t",
            "title": "Title",
            "evidence_refs": "not-a-list",
            "review_refs": None,
            "events": "not-a-list",
        }
    )
    assert record.evidence_refs == []
    assert record.review_refs == []
    assert record.events == []


def test_to_dict_includes_schema_version_constant():
    record = _new_lead()
    assert SCHEMA_VERSION == "1.0"
    assert record.to_dict()["schema_version"] == SCHEMA_VERSION


def test_utcnow_iso_is_timezone_aware_iso_format():
    from datetime import datetime

    value = utcnow_iso()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


# --- render_lead_state ------------------------------------------------------------


def test_render_lead_state_ok_for_valid_record():
    record = _new_lead()
    line = render_lead_state(record)
    assert line == "[lead_x] signal — Test lead (OK)"


# --- schema / example consistency -------------------------------------------------


def test_schema_state_enum_matches_module_lead_states():
    schema_path = REPO_ROOT / "schemas" / "trinity_schemas" / "trinity_lead_state_machine.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert set(schema["$defs"]["state"]["enum"]) == set(LEAD_STATES)


def test_schema_requires_rubric_fields_at_top_level():
    schema_path = REPO_ROOT / "schemas" / "trinity_schemas" / "trinity_lead_state_machine.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for rubric_field in ("claim", "scope", "mechanism", "falsifier", "repro_plan", "impact_boundary"):
        assert rubric_field in schema["required"]
        assert rubric_field in schema["properties"]


def test_example_file_conforms_to_schema_required_fields():
    schema_path = REPO_ROOT / "schemas" / "trinity_schemas" / "trinity_lead_state_machine.schema.json"
    example_path = REPO_ROOT / "examples" / "trinity_lead_state_machine.example.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    example = json.loads(example_path.read_text(encoding="utf-8"))
    for required_field in schema["required"]:
        assert required_field in example


def test_example_file_events_only_reference_known_states():
    example_path = REPO_ROOT / "examples" / "trinity_lead_state_machine.example.json"
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    for event in payload["events"]:
        assert event["to_state"] in LEAD_STATES
        assert event["from_state"] is None or event["from_state"] in LEAD_STATES


def test_example_file_event_chain_follows_allowed_transitions():
    example_path = REPO_ROOT / "examples" / "trinity_lead_state_machine.example.json"
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    for event in payload["events"]:
        if event["from_state"] is None:
            continue
        assert can_transition(event["from_state"], event["to_state"])
