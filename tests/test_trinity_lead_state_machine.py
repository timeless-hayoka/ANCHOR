from __future__ import annotations

import json

import pytest

from trinity_lead_state_machine import (
    LeadRecord,
    LeadTransitionError,
    apply_transition,
    can_transition,
    render_lead_state,
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
    """
    Populate the required hypothesis fields and promote a lead record to the hypothesis state.
    
    Parameters:
    	record (LeadRecord): The lead record to promote.
    
    Returns:
    	LeadRecord: The transitioned lead record.
    """
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
