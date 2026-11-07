"""Untrusted telemetry is a claim, never independent reproduction evidence."""
from __future__ import annotations

from typing import Any

PROOF_STATES = {"REPRODUCED_REAL", "COUNCIL_ACCEPTED", "REPORT_READY"}
EVENT_TYPES = {
    "case.started", "stage.started", "finding.detected", "finding.correlated",
    "poc.result", "case.completed", "log.line",
}


def provisional_state(state: str) -> str:
    state = state.upper()
    return "POC_EXECUTED_UNPROVEN" if state in PROOF_STATES else state


def validate_telemetry(event_type: str, payload: dict[str, Any]) -> None:
    if event_type not in EVENT_TYPES:
        raise ValueError("Unsupported producer event type; the server owns run lifecycle")
    if event_type != "log.line":
        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip() or len(case_id) > 256:
            raise ValueError("case_id must be a nonempty string of at most 256 characters")
    if "expected" in payload and (
        not isinstance(payload["expected"], list)
        or not all(isinstance(x, str) for x in payload["expected"])
    ):
        raise ValueError("expected must be a list of strings")
    if event_type == "poc.result":
        if type(payload.get("exploit_verified")) is not bool:
            raise ValueError("exploit_verified must be a JSON boolean")
        if "assertion_count" in payload and (
            type(payload["assertion_count"]) is not int or payload["assertion_count"] < 0
        ):
            raise ValueError("assertion_count must be a nonnegative integer")
    if event_type == "case.completed" and not isinstance(payload.get("validation_state"), str):
        raise ValueError("validation_state must be a string")
