from __future__ import annotations

import json

import pytest

from trinity_lead_state_machine import (
    ALLOWED_TRANSITIONS,
    LEAD_STATES,
    SCOPE_STATUSES,
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


def test_lead_event_to_dict_from_dict_round_trip():
    event = LeadEvent(
        event_id="evt_1",
        lead_id="lead_x",
        from_state="signal",
        to_state="hypothesis",
        actor="trinity",
        reason="promote",
        evidence_refs=("evidence/a.txt", "evidence/b.txt"),
        created_at="2026-07-03T00:00:00Z",
    )
    payload = event.to_dict()
    assert payload == {
        "event_id": "evt_1",
        "lead_id": "lead_x",
        "from_state": "signal",
        "to_state": "hypothesis",
        "actor": "trinity",
        "reason": "promote",
        "evidence_refs": ["evidence/a.txt", "evidence/b.txt"],
        "created_at": "2026-07-03T00:00:00Z",
    }
    restored = LeadEvent.from_dict(payload)
    assert restored.to_dict() == payload


def test_lead_event_from_dict_defaults_missing_fields():
    event = LeadEvent.from_dict({})
    assert event.event_id == ""
    assert event.lead_id == ""
    assert event.from_state is None
    assert event.to_state == ""
    assert event.actor == ""
    assert event.reason == ""
    assert event.evidence_refs == ()
    assert event.created_at == ""


def test_lead_event_from_dict_preserves_null_from_state():
    event = LeadEvent.from_dict({"from_state": None, "to_state": "signal"})
    assert event.from_state is None
    assert event.to_state == "signal"


def test_lead_record_defaults_to_signal_and_empty_rubric_fields():
    record = LeadRecord(lead_id="lead_y", target="target-y", title="Title y")
    assert record.state == "signal"
    assert record.scope_status == "unknown"
    assert record.claim == ""
    assert record.scope == ""
    assert record.mechanism == ""
    assert record.falsifier == ""
    assert record.repro_plan == ""
    assert record.impact_boundary == ""
    assert record.evidence_refs == []
    assert record.review_refs == []
    assert record.events == []


def test_validate_lead_reports_unknown_state_and_short_circuits():
    record = _new_lead()
    record.state = "bogus_state"
    errors = validate_lead(record)
    assert errors == ["unknown state 'bogus_state'"]


def test_validate_lead_reports_unknown_scope_status():
    record = _new_lead()
    record.scope_status = "bogus_scope"
    errors = validate_lead(record)
    assert any("unknown scope_status" in error for error in errors)


def test_validate_lead_reports_missing_identity_fields():
    record = LeadRecord(lead_id="", target="", title="")
    errors = validate_lead(record)
    assert "lead_id is required" in errors
    assert "target is required" in errors
    assert "title is required" in errors


def test_can_transition_returns_false_for_unknown_from_state():
    assert can_transition("bogus_state", "signal") is False


def test_apply_transition_rejects_unknown_target_state():
    record = _new_lead()
    with pytest.raises(LeadTransitionError, match="unknown target state"):
        apply_transition(record, to_state="bogus_state", actor="trinity", reason="broken", event_id="evt_1")


def test_needs_environment_round_trips_back_to_repro_attempted():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")

    record = apply_transition(
        record,
        to_state="needs_environment",
        actor="forge",
        reason="missing fork tooling",
        event_id="evt_3",
    )
    assert record.state == "needs_environment"
    assert validate_lead(record) == []

    record = apply_transition(
        record,
        to_state="repro_attempted",
        actor="forge",
        reason="environment fixed, retrying",
        event_id="evt_4",
    )
    assert record.state == "repro_attempted"
    assert validate_lead(record) == []


def test_needs_manual_review_can_fall_back_to_hypothesis():
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
        record,
        to_state="needs_manual_review",
        actor="council",
        reason="needs a human look",
        event_id="evt_4",
    )
    assert record.state == "needs_manual_review"
    assert validate_lead(record) == []

    record = apply_transition(
        record,
        to_state="hypothesis",
        actor="council",
        reason="sent back for more work",
        event_id="evt_5",
    )
    assert record.state == "hypothesis"


def test_apply_transition_deduplicates_evidence_refs_already_on_record():
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
    assert record.evidence_refs == ["evidence/forge_output.txt"]

    # Re-attaching the same evidence ref on a later transition does not
    # duplicate it, since it already exists on the record.
    record = apply_transition(
        record,
        to_state="needs_manual_review",
        actor="council",
        reason="reattach same evidence",
        event_id="evt_4",
        evidence_refs=["evidence/forge_output.txt"],
    )
    assert record.evidence_refs == ["evidence/forge_output.txt"]


def test_apply_transition_preserves_created_at_across_transitions():
    record = _new_lead()
    record.claim = "claim"
    record.scope = "scope"
    record.mechanism = "mechanism"
    record.falsifier = "falsifier"
    first = apply_transition(
        record,
        to_state="hypothesis",
        actor="trinity",
        reason="promote",
        event_id="evt_1",
        created_at="2026-07-03T00:00:00Z",
    )
    assert first.created_at == "2026-07-03T00:00:00Z"

    first.repro_plan = "repro plan"
    second = apply_transition(
        first,
        to_state="repro_attempted",
        actor="forge",
        reason="attempt",
        event_id="evt_2",
        created_at="2026-07-03T01:00:00Z",
    )
    assert second.created_at == "2026-07-03T00:00:00Z"
    assert second.updated_at == "2026-07-03T01:00:00Z"


def test_apply_transition_records_event_history_with_from_and_to_state():
    record = _promote_to_hypothesis(_new_lead())
    assert len(record.events) == 1
    event = record.events[0]
    assert event.from_state == "signal"
    assert event.to_state == "hypothesis"
    assert event.actor == "trinity"
    assert event.reason == "promote"


def test_render_lead_state_reports_ok_for_valid_record():
    record = _new_lead()
    line = render_lead_state(record)
    assert line == "[lead_x] signal — Test lead (OK)"


def test_terminal_states_constant_matches_expected_states():
    assert TERMINAL_STATES == frozenset({"report_ready", "rejected", "out_of_scope", "duplicate"})
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_lead_states_and_scope_statuses_are_stable():
    assert set(LEAD_STATES) == {
        "signal",
        "hypothesis",
        "repro_attempted",
        "reproduced_real",
        "council_accepted",
        "report_ready",
        "rejected",
        "out_of_scope",
        "duplicate",
        "needs_environment",
        "needs_manual_review",
    }
    assert SCOPE_STATUSES == frozenset({"authorized", "unknown", "out_of_scope"})


def test_utcnow_iso_returns_timezone_aware_iso_string():
    from datetime import datetime

    value = utcnow_iso()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_validate_lead_allows_report_ready_only_with_all_rubric_fields_and_refs():
    record = _new_lead()
    record.state = "report_ready"
    record.claim = "claim"
    record.scope = "scope"
    record.mechanism = "mechanism"
    record.falsifier = "falsifier"
    record.repro_plan = "repro plan"
    record.impact_boundary = "impact boundary"
    record.evidence_refs = ["evidence/a.txt"]
    record.review_refs = ["reviews/a.md"]
    assert validate_lead(record) == []

    record.review_refs = []
    errors = validate_lead(record)
    assert any("review_refs" in error for error in errors)
