"""Machine-readable state machine for Trinity leads.

A plausible claim is not a finding (see TRINITY_RUBRIC.md). This module gives
that rule a schema: leads move through an explicit, evidence-gated lifecycle
and cannot be promoted to report_ready without reproduction and impact
evidence attached along the way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0"

LEAD_STATES = (
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
)

TERMINAL_STATES = frozenset({"report_ready", "rejected", "out_of_scope", "duplicate"})

SCOPE_STATUSES = frozenset({"authorized", "unknown", "out_of_scope"})

# Canonical transition graph. A lead may only move to a state listed for its
# current state; anything else is an illegal transition.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "signal": frozenset({"hypothesis", "rejected", "out_of_scope", "duplicate"}),
    "hypothesis": frozenset({"repro_attempted", "rejected", "out_of_scope", "duplicate", "needs_manual_review"}),
    "repro_attempted": frozenset({"reproduced_real", "needs_environment", "rejected", "out_of_scope"}),
    "needs_environment": frozenset({"repro_attempted", "rejected"}),
    "reproduced_real": frozenset({"council_accepted", "needs_manual_review", "rejected"}),
    "needs_manual_review": frozenset({"council_accepted", "hypothesis", "rejected"}),
    "council_accepted": frozenset({"report_ready", "rejected"}),
    "report_ready": frozenset(),
    "rejected": frozenset(),
    "out_of_scope": frozenset(),
    "duplicate": frozenset(),
}

# Fields required by the Trinity rubric (claim, mechanism, falsifier, repro
# plan, impact boundary) that must be non-empty once a lead reaches a given
# state. Each state's requirement set is cumulative over the canonical path.
REQUIRED_FIELDS_BY_STATE: dict[str, tuple[str, ...]] = {
    "signal": (),
    "hypothesis": ("claim", "scope", "mechanism", "falsifier"),
    "repro_attempted": ("claim", "scope", "mechanism", "falsifier", "repro_plan"),
    "needs_environment": ("claim", "scope", "mechanism", "falsifier", "repro_plan"),
    "reproduced_real": ("claim", "scope", "mechanism", "falsifier", "repro_plan"),
    "needs_manual_review": ("claim", "scope", "mechanism", "falsifier", "repro_plan"),
    "council_accepted": ("claim", "scope", "mechanism", "falsifier", "repro_plan", "impact_boundary"),
    "report_ready": ("claim", "scope", "mechanism", "falsifier", "repro_plan", "impact_boundary"),
    "rejected": (),
    "out_of_scope": (),
    "duplicate": (),
}

# States from which evidence_refs must already contain at least one entry
# before the lead may sit in that state (reproduction proof).
STATES_REQUIRING_EVIDENCE = frozenset({"reproduced_real", "council_accepted", "report_ready"})

# States from which review_refs must already contain at least one entry
# (council sign-off) before the lead may sit in that state.
STATES_REQUIRING_REVIEW = frozenset({"council_accepted", "report_ready"})


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LeadTransitionError(ValueError):
    """Raised when a transition or field-completeness rule is violated."""


@dataclass(frozen=True)
class LeadEvent:
    event_id: str
    lead_id: str
    from_state: str | None
    to_state: str
    actor: str
    reason: str
    evidence_refs: tuple[str, ...] = ()
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "lead_id": self.lead_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LeadEvent:
        evidence_refs = payload.get("evidence_refs")
        return cls(
            event_id=str(payload.get("event_id") or ""),
            lead_id=str(payload.get("lead_id") or ""),
            from_state=payload.get("from_state"),
            to_state=str(payload.get("to_state") or ""),
            actor=str(payload.get("actor") or ""),
            reason=str(payload.get("reason") or ""),
            evidence_refs=tuple(evidence_refs) if isinstance(evidence_refs, list) else (),
            created_at=str(payload.get("created_at") or ""),
        )


@dataclass
class LeadRecord:
    lead_id: str
    target: str
    title: str
    state: str = "signal"
    scope_status: str = "unknown"
    claim: str = ""
    scope: str = ""
    mechanism: str = ""
    falsifier: str = ""
    repro_plan: str = ""
    impact_boundary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    review_refs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    events: list[LeadEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "lead_id": self.lead_id,
            "target": self.target,
            "scope_status": self.scope_status,
            "state": self.state,
            "title": self.title,
            "claim": self.claim,
            "scope": self.scope,
            "mechanism": self.mechanism,
            "falsifier": self.falsifier,
            "repro_plan": self.repro_plan,
            "impact_boundary": self.impact_boundary,
            "evidence_refs": list(self.evidence_refs),
            "review_refs": list(self.review_refs),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LeadRecord:
        events_raw = payload.get("events")
        events = [LeadEvent.from_dict(item) for item in events_raw] if isinstance(events_raw, list) else []
        evidence_refs = payload.get("evidence_refs")
        review_refs = payload.get("review_refs")
        return cls(
            lead_id=str(payload.get("lead_id") or ""),
            target=str(payload.get("target") or ""),
            title=str(payload.get("title") or ""),
            state=str(payload.get("state") or "signal"),
            scope_status=str(payload.get("scope_status") or "unknown"),
            claim=str(payload.get("claim") or ""),
            scope=str(payload.get("scope") or ""),
            mechanism=str(payload.get("mechanism") or ""),
            falsifier=str(payload.get("falsifier") or ""),
            repro_plan=str(payload.get("repro_plan") or ""),
            impact_boundary=str(payload.get("impact_boundary") or ""),
            evidence_refs=list(evidence_refs) if isinstance(evidence_refs, list) else [],
            review_refs=list(review_refs) if isinstance(review_refs, list) else [],
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            events=events,
        )


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def validate_lead(record: LeadRecord) -> list[str]:
    """Return a list of validation error strings; empty means the record is
    internally consistent for the state it currently claims to be in."""
    errors: list[str] = []

    if record.state not in LEAD_STATES:
        errors.append(f"unknown state '{record.state}'")
        return errors

    if record.scope_status not in SCOPE_STATUSES:
        errors.append(f"unknown scope_status '{record.scope_status}'")

    if not record.lead_id.strip():
        errors.append("lead_id is required")
    if not record.target.strip():
        errors.append("target is required")
    if not record.title.strip():
        errors.append("title is required")

    for required_field in REQUIRED_FIELDS_BY_STATE.get(record.state, ()):
        if not str(getattr(record, required_field, "")).strip():
            errors.append(f"state '{record.state}' requires non-empty field '{required_field}'")

    if record.state in STATES_REQUIRING_EVIDENCE and not record.evidence_refs:
        errors.append(f"state '{record.state}' requires at least one evidence_refs entry")

    if record.state in STATES_REQUIRING_REVIEW and not record.review_refs:
        errors.append(f"state '{record.state}' requires at least one review_refs entry")

    return errors


def apply_transition(
    record: LeadRecord,
    *,
    to_state: str,
    actor: str,
    reason: str,
    event_id: str,
    evidence_refs: list[str] | None = None,
    created_at: str | None = None,
) -> LeadRecord:
    """Return a new LeadRecord advanced to to_state, or raise
    LeadTransitionError if the transition or resulting state is invalid."""
    if to_state not in LEAD_STATES:
        raise LeadTransitionError(f"unknown target state '{to_state}'")
    if not can_transition(record.state, to_state):
        raise LeadTransitionError(f"illegal transition from '{record.state}' to '{to_state}'")

    timestamp = created_at or utcnow_iso()
    refs = list(evidence_refs or [])

    next_record = LeadRecord(
        lead_id=record.lead_id,
        target=record.target,
        title=record.title,
        state=to_state,
        scope_status=record.scope_status,
        claim=record.claim,
        scope=record.scope,
        mechanism=record.mechanism,
        falsifier=record.falsifier,
        repro_plan=record.repro_plan,
        impact_boundary=record.impact_boundary,
        evidence_refs=list(record.evidence_refs) + [ref for ref in refs if ref not in record.evidence_refs],
        review_refs=list(record.review_refs),
        created_at=record.created_at or timestamp,
        updated_at=timestamp,
        events=list(record.events)
        + [
            LeadEvent(
                event_id=event_id,
                lead_id=record.lead_id,
                from_state=record.state,
                to_state=to_state,
                actor=actor,
                reason=reason,
                evidence_refs=tuple(refs),
                created_at=timestamp,
            )
        ],
    )

    errors = validate_lead(next_record)
    if errors:
        raise LeadTransitionError("; ".join(errors))

    return next_record


def render_lead_state(record: LeadRecord) -> str:
    """One-line, console/run-log friendly summary of a lead's current state."""
    errors = validate_lead(record)
    status = "OK" if not errors else f"INVALID ({'; '.join(errors)})"
    return f"[{record.lead_id}] {record.state} — {record.title} ({status})"
