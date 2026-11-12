"""Fail-closed Finder -> Foundry -> Trinity Watcher -> Council evidence handoff.

This validates supplied artifacts and state transitions; it does NOT independently
authenticate RPC responses, source equivalence, signatures, or on-chain impact.
Never use fixture success as proof of a real vulnerability.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from trinity_lead_state_machine import (
    LeadRecord, LeadTransitionError, apply_transition, validate_lead,
)

_HASH = re.compile(r"^[0-9a-f]{64}$")
_BLOCK = re.compile(r"^0x[0-9a-fA-F]{64}$")


class HandoffRejected(ValueError):
    """The evidence bundle did not pass the handoff gate."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffRejected(message)


def _artifact(value: object, label: str) -> Mapping:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _string(obj: Mapping, key: str, label: str) -> str:
    value = obj.get(key)
    _require(isinstance(value, str) and bool(value.strip()), f"{label}.{key} missing")
    return value


def _refs(obj: Mapping, label: str) -> list[str]:
    value = obj.get("evidence_refs")
    _require(isinstance(value, list) and len(value) > 0, f"{label} evidence_refs missing")
    _require(all(isinstance(x, str) and x.strip() and len(x) <= 1024 for x in value),
             f"{label} evidence_refs invalid")
    _require(len(value) == len(set(value)), f"{label} duplicate evidence refs")
    return list(value)


def review_case(finder: Mapping, foundry: Mapping, watcher: Mapping,
                council: Mapping) -> LeadRecord:
    """Transition one prevalidated evidence bundle; reject missing/contradictory claims.

    Scope and proof identities are externally supplied, not cryptographically
    authenticated here. All four artifacts are required; no partial promotion.
    """
    finder = _artifact(finder, "finder")
    foundry = _artifact(foundry, "foundry")
    watcher = _artifact(watcher, "watcher")
    council = _artifact(council, "council")
    case_id = _string(finder, "case_id", "finder")
    _require(len(case_id) <= 128, "case_id too long")
    for label, item in (("foundry", foundry), ("watcher", watcher), ("council", council)):
        _require(item.get("case_id") == case_id, f"{label} case identity mismatch")
    _require(finder.get("scope_status") == "authorized", "scope not authorized")
    target = _string(finder, "target", "finder")
    claim = _string(finder, "claim", "finder")
    scope = _string(finder, "scope", "finder")
    mechanism = _string(finder, "mechanism", "finder")
    falsifier = _string(finder, "falsifier", "finder")
    _string(finder, "scope_evidence_ref", "finder")
    _require(finder.get("duplicate_status") == "clear", "duplicate status unresolved")
    repro_plan = _string(foundry, "repro_plan", "foundry")
    _require(foundry.get("target") == target, "Foundry target mismatch")
    _require(foundry.get("scope_evidence_ref") == finder.get("scope_evidence_ref"),
             "scope evidence changed")
    _require(foundry.get("status") == "reproduced_real", "reproduction unproven")
    _require(foundry.get("negative_control_passed") is True, "negative control failed")
    _require(foundry.get("source_equivalence") == "proven", "source equivalence unproven")
    _require(type(foundry.get("chain_id")) is int and foundry["chain_id"] > 0,
             "chain ID invalid")
    _require(type(foundry.get("block_number")) is int and foundry["block_number"] > 0,
             "block number invalid")
    _require(isinstance(foundry.get("block_hash"), str)
             and bool(_BLOCK.fullmatch(foundry["block_hash"])), "block hash invalid")
    _require(isinstance(foundry.get("runtime_sha256"), str)
             and bool(_HASH.fullmatch(foundry["runtime_sha256"])), "runtime hash invalid")
    proof_refs = _refs(foundry, "foundry")
    _require(watcher.get("verdict") == "validated", "Watcher did not validate")
    _require(watcher.get("reviewed_evidence_refs") == proof_refs, "Watcher did not review this proof")
    prover_actor = _string(foundry, "actor", "foundry").strip().casefold()
    watcher_actor = _string(watcher, "actor", "watcher").strip().casefold()
    _require(watcher_actor != prover_actor, "Watcher not independent of prover")
    challenge = _string(watcher, "challenge", "watcher")
    watcher_refs = _refs(watcher, "watcher")
    _require(council.get("verdict") == "accepted", "Council did not accept")
    council_actor = _string(council, "actor", "council").strip().casefold()
    _require(council_actor not in (prover_actor, watcher_actor),
             "Council not independent")
    impact = _string(council, "impact_boundary", "council")
    _require(council.get("reviewed_evidence_refs") == proof_refs,
             "Council did not review this proof")
    review_refs = _refs(council, "council")

    record = LeadRecord(lead_id=case_id, target=target, title=claim,
                        scope_status="authorized", claim=claim, scope=scope,
                        mechanism=mechanism, falsifier=falsifier, repro_plan=repro_plan)
    steps = (
        ("hypothesis", "finder", "Scoped hypothesis", []),
        ("repro_attempted", foundry["actor"], "Attempt logged", []),
        ("reproduced_real", foundry["actor"], "Reproduction artifact supplied", proof_refs),
    )
    for i, (state, actor, reason, refs) in enumerate(steps, start=1):
        record = apply_transition(record, to_state=state, actor=actor, reason=reason,
                                  event_id=f"{case_id}:{i}", evidence_refs=refs)
    record.watcher_challenge = challenge
    record.watcher_verdict = "validated"
    record.watcher_refs = watcher_refs
    record = apply_transition(record, to_state="watcher_reviewed",
                              actor=watcher["actor"], reason="Independent challenge",
                              event_id=f"{case_id}:4")
    record.impact_boundary = impact
    record.review_refs = review_refs
    record = apply_transition(record, to_state="council_accepted",
                              actor=council["actor"], reason="Independent council approval",
                              event_id=f"{case_id}:5")
    _require(not validate_lead(record), "lead failed canonical state validation")
    # Intentionally do not advance to report_ready: requires a separate human gate.
    return record
