#!/usr/bin/env python3
"""Create a non-operational Trinity signal from ANCHOR deployment evidence.

The handoff is a triage artifact, not a scope grant, reproduction, or finding.
Input files are untrusted snapshots; neither source status nor CI success can
automatically promote Trinity beyond the initial signal state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trinity_lead_state_machine import LeadRecord, validate_lead

HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
TARGET = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REQUIRED_CHECKS = ("identity", "discovery", "scope", "source_file")
MAX_BYTES = 5_000_000


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("input exceeds maximum size")
    return json.loads(raw.decode("utf-8"))


def prepare_handoff(readiness: Any, source_evidence: Any, build_evidence: Any = None) -> dict[str, Any]:
    """Validate provenance and emit a Trinity *signal only* on success.

    A valid handoff can be BLOCKED: that is expected for incomplete research.
    Reject contradictory, malformed or cross-target evidence rather than
    issuing a plausible-looking lead.
    """
    if not isinstance(readiness, dict) or not isinstance(source_evidence, dict):
        raise ValueError("readiness and source evidence must be JSON objects")
    target_id = readiness.get("target_id")
    target_ref = readiness.get("target_ref")
    chain_id = readiness.get("chain_id")
    address = readiness.get("contract_address")
    if not isinstance(target_id, str) or not TARGET.fullmatch(target_id):
        raise ValueError("invalid target identity")
    if not isinstance(target_ref, str) or not HEX40.fullmatch(target_ref):
        raise ValueError("target revision must be a full commit SHA")
    if not isinstance(chain_id, str) or not chain_id.isdigit() or int(chain_id) <= 0:
        raise ValueError("invalid chain identity")
    if not isinstance(address, str) or not ADDRESS.fullmatch(address):
        raise ValueError("invalid deployed contract address")
    if (
        str(source_evidence.get("chain_id")) != chain_id
        or str(source_evidence.get("address", "")).lower() != address.lower()
    ):
        raise ValueError("source evidence references a different deployment")
    if readiness.get("analysis_authorization_issued") is not False:
        raise ValueError("readiness must not assert that it issued authorization")
    if readiness.get("full_deployment_equivalence") != "NOT_PROVEN":
        raise ValueError("unexpected deployment parity assertion in readiness")
    if readiness.get("foundry_reproduction") != "NOT_EVALUATED":
        raise ValueError("readiness must not claim reproduction")
    if readiness.get("trinity_finding_status") != "NOT_EVALUATED":
        raise ValueError("readiness must not claim Trinity acceptance")
    checks = readiness.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED_CHECKS):
        raise ValueError("incomplete readiness checks")
    states = []
    for name in REQUIRED_CHECKS:
        detail = checks[name]
        if (
            not isinstance(detail, dict)
            or detail.get("state") not in ("PASS", "BLOCKED")
            or not isinstance(detail.get("detail"), str)
            or not detail["detail"].strip()
        ):
            raise ValueError(f"invalid readiness check: {name}")
        states.append(detail["state"])
    full_pass = all(state == "PASS" for state in states)
    status = readiness.get("status")
    if status not in ("BLOCKED", "SOURCE_REVIEW_GATES_PASSED"):
        raise ValueError("invalid readiness status")
    if (status == "SOURCE_REVIEW_GATES_PASSED") != full_pass:
        raise ValueError("readiness status contradicts its check states")
    source_status = source_evidence.get("status")
    if source_status not in (
        "NOT_VERIFIED", "PINNED_SOURCE_MATCH",
        "PINNED_SOURCE_MATCH_NONEXACT_RUNTIME",
    ):
        raise ValueError("unknown source verification status")
    if checks["source_file"]["state"] == "PASS":
        if (
            source_status != "PINNED_SOURCE_MATCH"
            or source_evidence.get("reported_runtime_match") != "exact_match"
        ):
            raise ValueError("source check passes despite insufficient source verification")
    if status == "SOURCE_REVIEW_GATES_PASSED" and source_status != "PINNED_SOURCE_MATCH":
        raise ValueError("source evidence contradicts positive readiness")

    build_state = "NOT_SUPPLIED"
    if build_evidence is not None:
        if not isinstance(build_evidence, dict):
            raise ValueError("build evidence must be a JSON object")
        if build_evidence.get("state") == "PROVIDER_BUILD_COMPILED":
            if (
                str(build_evidence.get("chain_id")) != chain_id
                or str(build_evidence.get("address", "")).lower() != address.lower()
            ):
                raise ValueError("build evidence belongs to another deployment")
            if build_evidence.get("compiler_equals_provider_recompiled") is not True:
                build_state = "COMPILED_PROVIDER_BYTECODE_DIFFERENT"
            else:
                expected_sources = source_evidence.get("verified_source_candidates")
                verified_hashes = {
                    item["sha256"] for item in expected_sources
                    if isinstance(item, dict) and isinstance(item.get("sha256"), str)
                } if isinstance(expected_sources, list) else set()
                source_hash = build_evidence.get("source_sha256")
                if verified_hashes and source_hash not in verified_hashes:
                    raise ValueError("build source hash contradicts verified source record")
                build_state = (
                    "PROVIDER_RECOMPILE_MATCH_SOURCE_LINKED"
                    if verified_hashes else "PROVIDER_RECOMPILE_MATCH_SOURCE_UNBOUND"
                )
        elif build_evidence.get("state") == "COMPILE_NOT_PROVEN":
            build_state = "COMPILE_NOT_PROVEN"
        else:
            raise ValueError("unsupported build evidence state")

    key = f"{target_id.lower()}|{target_ref.lower()}|{chain_id}|{address.lower()}"
    lead_id = "anchor_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    record = LeadRecord(
        lead_id=lead_id,
        target=target_id,
        title=f"Deployment source review: {target_id} on chain {chain_id}",
        state="signal",
        # Scope grants are operator-controlled. This read-only handoff does not
        # confer them even when the readiness snapshot has a scope check PASS.
        scope_status="unknown",
    )
    errors = validate_lead(record)
    if errors:
        raise ValueError("Trinity signal invalid: " + "; ".join(errors))
    return {
        "schema_version": "1.0",
        "handoff_status": "SOURCE_REVIEW_ONLY" if full_pass else "BLOCKED_RESEARCH_SIGNAL",
        "lead": record.to_dict(),
        "deployment": {
            "target_id": target_id,
            "target_ref": target_ref,
            "chain_id": chain_id,
            "contract_address": address.lower(),
        },
        "provenance": {
            "readiness_sha256": canonical_digest(readiness),
            "source_evidence_sha256": canonical_digest(source_evidence),
            "build_evidence_sha256": canonical_digest(build_evidence) if build_evidence is not None else None,
            "build_state": build_state,
            "source_status": source_status,
            "source_runtime_match": source_evidence.get("reported_runtime_match"),
            "readiness_status": status,
            "checks": {name: checks[name]["state"] for name in REQUIRED_CHECKS},
        },
        "deployment_bytecode_equivalence": "NOT_PROVEN",
        "reproduction": "NOT_ATTEMPTED",
        "finding": "NONE",
        "authorization_grant_issued": False,
        "next_required_step": (
            "Resolve readiness blockers and verify deployed bytecode; "
            "use a separate operator-controlled scope grant before analysis. "
            "Do not promote this signal automatically."
        ),
    }


def write_new_file(path: Path, payload: dict[str, Any]) -> None:
    """Fail if file exists; atomically publish a new immutable review artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".anchor-handoff-", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        # Exclusive link avoids clobbering an existing lead/evidence artifact.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness", required=True, type=Path)
    parser.add_argument("--source-evidence", required=True, type=Path)
    parser.add_argument("--build-evidence", type=Path, help="Optional isolated compiler report")
    parser.add_argument("--output", type=Path, help="Create new handoff JSON; never overwrite")
    args = parser.parse_args(argv)
    try:
        payload = prepare_handoff(
            read_json(args.readiness), read_json(args.source_evidence),
            read_json(args.build_evidence) if args.build_evidence else None,
        )
        if args.output is not None:
            write_new_file(args.output, payload)
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        print(json.dumps({
            "handoff_status": "REJECTED",
            "reason": f"{type(exc).__name__}: {exc}",
            "lead_created": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
