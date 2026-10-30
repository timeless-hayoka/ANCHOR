from __future__ import annotations

import json

import pytest

from trinity_lead_state_machine import (
    SCHEMA_VERSION,
    LeadEvent,
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
    assert can_transition("reproduced_real", "watcher_reviewed")
    assert can_transition("watcher_reviewed", "council_accepted")
    assert can_transition("watcher_reviewed", "hypothesis")
    assert not can_transition("reproduced_real", "council_accepted")
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


def _reproduce(record: LeadRecord) -> LeadRecord:
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")
    return apply_transition(
        record,
        to_state="reproduced_real",
        actor="evidence-gate",
        reason="repro demonstrated",
        event_id="evt_3",
        evidence_refs=["evidence/forge_output.txt"],
    )


def test_reproduced_lead_cannot_skip_watcher():
    record = _reproduce(_promote_to_hypothesis(_new_lead()))
    assert not can_transition(record.state, "council_accepted")
    with pytest.raises(LeadTransitionError, match="illegal transition"):
        apply_transition(record, to_state="council_accepted", actor="council", reason="skip watcher", event_id="evt_4")


def test_watcher_review_requires_independent_artifact_and_verdict():
    record = _reproduce(_promote_to_hypothesis(_new_lead()))
    record.watcher_challenge = "Attempted alternate explanations, invariant checks, and negative controls."

    with pytest.raises(LeadTransitionError, match="watcher_refs"):
        apply_transition(record, to_state="watcher_reviewed", actor="watcher", reason="challenged", event_id="evt_4")

    record.watcher_refs = ["reviews/watcher_review.md"]
    with pytest.raises(LeadTransitionError, match="completed watcher_verdict"):
        apply_transition(record, to_state="watcher_reviewed", actor="watcher", reason="challenged", event_id="evt_4")


def test_discredited_watcher_verdict_cannot_reach_council():
    record = _reproduce(_promote_to_hypothesis(_new_lead()))
    record.watcher_challenge = "Negative control showed the claimed loss was test-fixture contamination."
    record.watcher_refs = ["reviews/watcher_review.md"]
    record.watcher_verdict = "discredited"
    record = apply_transition(record, to_state="watcher_reviewed", actor="watcher", reason="claim discredited", event_id="evt_4")

    record.impact_boundary = "claimed impact"
    record.review_refs = ["reviews/council_review.md"]
    with pytest.raises(LeadTransitionError, match="watcher_verdict 'validated'"):
        apply_transition(record, to_state="council_accepted", actor="council", reason="incorrect acceptance", event_id="evt_5")


def test_watcher_can_send_claim_back_to_hypothesis():
    record = _reproduce(_promote_to_hypothesis(_new_lead()))
    record.watcher_challenge = "Mechanism reproduced, but the causal explanation conflicts with the trace."
    record.watcher_refs = ["reviews/watcher_review.md"]
    record.watcher_verdict = "inconclusive"
    record = apply_transition(record, to_state="watcher_reviewed", actor="watcher", reason="reframe required", event_id="evt_4")
    record = apply_transition(record, to_state="hypothesis", actor="watcher", reason="rewrite mechanism and falsifier", event_id="evt_5")
    assert record.state == "hypothesis"


def test_promotion_to_report_ready_requires_reproduction_watcher_and_council():
    record = _reproduce(_promote_to_hypothesis(_new_lead()))
    record.watcher_challenge = "Tried alternate call ordering, benign controls, stale-state checks, and impact minimization."
    record.watcher_refs = ["reviews/watcher_review.md"]
    record.watcher_verdict = "validated"
    record = apply_transition(record, to_state="watcher_reviewed", actor="watcher", reason="survived falsification", event_id="evt_4")

    record.impact_boundary = "impact boundary"
    with pytest.raises(LeadTransitionError, match="review_refs"):
        apply_transition(record, to_state="council_accepted", actor="council", reason="no council artifact", event_id="evt_5")

    record.review_refs = ["reviews/council_review.md"]
    record = apply_transition(record, to_state="council_accepted", actor="council", reason="accepted", event_id="evt_5")
    record = apply_transition(record, to_state="report_ready", actor="anchor", reason="archived", event_id="evt_6")
    assert record.state == "report_ready"
    assert validate_lead(record) == []
    assert len(record.events) == 6


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
    record.state = "hypothesis"
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


def test_validate_lead_rejects_unknown_state():
    record = _new_lead()
    record.state = "bogus_state"
    errors = validate_lead(record)
    assert errors == ["unknown state 'bogus_state'"]


def test_validate_lead_rejects_unknown_scope_status():
    record = _new_lead()
    record.scope_status = "bogus_scope"
    errors = validate_lead(record)
    assert errors == ["unknown scope_status 'bogus_scope'"]


def test_validate_lead_requires_lead_id_target_and_title():
    record = LeadRecord(lead_id="   ", target="", title="")
    errors = validate_lead(record)
    assert "lead_id is required" in errors
    assert "target is required" in errors
    assert "title is required" in errors


def test_needs_environment_round_trip_back_to_repro_attempted():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")

    record = apply_transition(
        record, to_state="needs_environment", actor="forge", reason="missing fork", event_id="evt_3"
    )
    assert record.state == "needs_environment"
    assert validate_lead(record) == []

    record = apply_transition(
        record, to_state="repro_attempted", actor="forge", reason="environment restored", event_id="evt_4"
    )
    assert record.state == "repro_attempted"
    assert validate_lead(record) == []


def test_needs_manual_review_can_fall_back_to_hypothesis_or_advance():
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

    review_needed = apply_transition(
        record, to_state="needs_manual_review", actor="council", reason="ambiguous impact", event_id="evt_4"
    )
    assert review_needed.state == "needs_manual_review"
    assert validate_lead(review_needed) == []

    fallback = apply_transition(
        review_needed, to_state="hypothesis", actor="council", reason="send back", event_id="evt_5"
    )
    assert fallback.state == "hypothesis"

    review_needed.impact_boundary = "impact boundary"
    review_needed.review_refs = ["reviews/council_review.md"]
    advanced = apply_transition(
        review_needed, to_state="council_accepted", actor="council", reason="accepted after review", event_id="evt_5"
    )
    assert advanced.state == "council_accepted"


def test_apply_transition_rejects_unknown_target_state():
    record = _new_lead()
    with pytest.raises(LeadTransitionError, match="unknown target state"):
        apply_transition(record, to_state="not_a_real_state", actor="trinity", reason="typo", event_id="evt_1")


def test_apply_transition_deduplicates_evidence_refs_already_on_record():
    record = _promote_to_hypothesis(_new_lead())
    record.repro_plan = "repro plan"
    record = apply_transition(record, to_state="repro_attempted", actor="forge", reason="attempt", event_id="evt_2")

    record = apply_transition(
        record,
        to_state="needs_environment",
        actor="forge",
        reason="missing fork",
        event_id="evt_3",
        evidence_refs=["evidence/one.txt"],
    )
    assert record.evidence_refs == ["evidence/one.txt"]

    record = apply_transition(
        record,
        to_state="repro_attempted",
        actor="forge",
        reason="environment restored",
        event_id="evt_4",
        evidence_refs=["evidence/one.txt"],
    )
    assert record.evidence_refs == ["evidence/one.txt"]


def test_render_lead_state_reports_ok_for_valid_record():
    record = _new_lead()
    line = render_lead_state(record)
    assert line == "[lead_x] signal — Test lead (OK)"


def test_lead_event_to_dict_and_from_dict_round_trip():
    event = LeadEvent(
        event_id="evt_1",
        lead_id="lead_x",
        from_state=None,
        to_state="signal",
        actor="trinity",
        reason="initial signal",
        evidence_refs=("evidence/one.txt",),
        created_at="2026-07-03T00:00:00Z",
    )
    payload = event.to_dict()
    assert payload == {
        "event_id": "evt_1",
        "lead_id": "lead_x",
        "from_state": None,
        "to_state": "signal",
        "actor": "trinity",
        "reason": "initial signal",
        "evidence_refs": ["evidence/one.txt"],
        "created_at": "2026-07-03T00:00:00Z",
    }
    restored = LeadEvent.from_dict(payload)
    assert restored == event


def test_to_dict_always_stamps_current_schema_version():
    record = _new_lead()
    payload = record.to_dict()
    assert payload["schema_version"] == SCHEMA_VERSION

    payload["schema_version"] = "0.1"
    restored = LeadRecord.from_dict(payload)
    assert restored.to_dict()["schema_version"] == SCHEMA_VERSION


def test_from_dict_defaults_missing_optional_fields():
    record = LeadRecord.from_dict({"lead_id": "lead_z", "target": "t", "title": "T"})
    assert record.state == "signal"
    assert record.scope_status == "unknown"
    assert record.evidence_refs == []
    assert record.review_refs == []
    assert record.events == []
    assert validate_lead(record) == []
