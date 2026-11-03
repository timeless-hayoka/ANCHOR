#!/usr/bin/env python3
"""Evidence-first readiness report for an ANCHOR smart-contract hunt.

Read-only: does not issue authorization grants, fetch RPC data, run exploits,
or promote hypotheses to findings. A source-file match is NOT bytecode parity.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bugbot.scope import ANALYSIS, IDENTITY_VERIFIED_REPO, validate_grant_for_request
from bugbot.scope_confirmation import build_scope_grant_from_confirmation

COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def assess(
    *,
    target_id: str,
    target_ref: str,
    chain_id: str,
    contract_address: str,
    anchor_root: Path,
    discovery: Any = None,
    scope_confirmation: Path | None = None,
    source_evidence: Any = None,
) -> dict[str, Any]:
    """Check independent evidence gates; never infer eligibility from a score."""
    checks: dict[str, dict[str, str]] = {}

    def blocked(stage: str, detail: str) -> None:
        checks[stage] = {"state": "BLOCKED", "detail": detail}

    def passed(stage: str, detail: str) -> None:
        checks[stage] = {"state": "PASS", "detail": detail}

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", target_id):
        blocked("identity", "target_id must be exact owner/repository")
    elif not COMMIT_SHA.fullmatch(target_ref):
        blocked("identity", "target_ref must be an immutable 40-character commit SHA")
    else:
        passed("identity", "repository and immutable source revision supplied")

    candidates = discovery.get("candidates") if isinstance(discovery, dict) else None
    if not isinstance(candidates, list):
        blocked("discovery", "missing or malformed passive-discovery bundle")
    else:
        matches = [row for row in candidates if isinstance(row, dict) and row.get("full_name") == target_id]
        if len(matches) != 1:
            blocked("discovery", "exactly one matching candidate required")
        elif matches[0].get("scan_status") != "complete" or matches[0].get("scan_errors"):
            blocked("discovery", "candidate enrichment incomplete, errored or metadata only")
        else:
            passed("discovery", "complete passive metadata scan (not scope authorization)")

    if scope_confirmation is None:
        blocked("scope", "no reviewer-approved scope confirmation supplied")
    elif checks["identity"]["state"] != "PASS":
        blocked("scope", "identity not pinned")
    else:
        grant, error = build_scope_grant_from_confirmation(scope_confirmation, anchor_root=anchor_root)
        if grant is None:
            blocked("scope", error or "invalid scope confirmation")
        elif grant.identity_status != IDENTITY_VERIFIED_REPO:
            blocked("scope", "selected GitHub target requires verified_repo identity")
        elif grant.target_repo_url != f"https://github.com/{target_id}":
            blocked("scope", "policy confirmation repository URL does not match")
        else:
            denial = validate_grant_for_request(
                grant, target_id=target_id, target_ref=target_ref, action=ANALYSIS
            )
            if denial is not None:
                blocked("scope", f"scope gate denied: {denial}")
            else:
                passed("scope", "reviewed evidence permits analysis of this exact revision")

    if not isinstance(source_evidence, dict):
        blocked("source_file", "missing source verifier output")
    elif not chain_id.isdigit() or not re.fullmatch(r"0x[a-fA-F0-9]{40}", contract_address):
        blocked("source_file", "invalid chain ID or deployed contract address")
    elif str(source_evidence.get("chain_id")) != chain_id or str(source_evidence.get("address", "")).lower() != contract_address.lower():
        blocked("source_file", "source evidence does not match the requested deployment")
    elif source_evidence.get("status") != "PINNED_SOURCE_MATCH":
        blocked("source_file", "source not exact-runtime verified or pinned file differs")
    elif source_evidence.get("reported_runtime_match") != "exact_match":
        blocked("source_file", "runtime verification is not exact")
    elif not (
        isinstance(source_evidence.get("matched_source_paths"), list)
        and source_evidence["matched_source_paths"]
        and all(isinstance(path, str) and path.strip() for path in source_evidence["matched_source_paths"])
    ):
        blocked("source_file", "matched verified source paths missing or malformed")
    elif not re.fullmatch(r"[a-fA-F0-9]{64}", str(source_evidence.get("source_sha256", ""))):
        blocked("source_file", "missing pinned-source content hash")
    else:
        passed("source_file", "one pinned source file matched exact-runtime verified source; not full build parity")

    all_pass = all(v["state"] == "PASS" for v in checks.values())
    return {
        "target_id": target_id,
        "target_ref": target_ref,
        "chain_id": chain_id,
        "contract_address": contract_address,
        "status": "SOURCE_REVIEW_GATES_PASSED" if all_pass else "BLOCKED",
        "checks": checks,
        "full_deployment_equivalence": "NOT_PROVEN",
        "foundry_reproduction": "NOT_EVALUATED",
        "trinity_finding_status": "NOT_EVALUATED",
        "analysis_authorization_issued": False,
        "note": "Readiness is evidence triage only. It never issues an operational grant or authorizes live testing.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--target-ref", required=True)
    parser.add_argument("--chain-id", required=True)
    parser.add_argument("--contract-address", required=True)
    parser.add_argument("--discovery-bundle", type=Path)
    parser.add_argument("--scope-confirmation", type=Path)
    parser.add_argument("--source-evidence", type=Path)
    parser.add_argument("--anchor-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        discovery = json.loads(args.discovery_bundle.read_text(encoding="utf-8")) if args.discovery_bundle else None
        source = json.loads(args.source_evidence.read_text(encoding="utf-8")) if args.source_evidence else None
        result = assess(
            target_id=args.target_id, target_ref=args.target_ref,
            chain_id=args.chain_id, contract_address=args.contract_address,
            anchor_root=args.anchor_root.resolve(),
            discovery=discovery, scope_confirmation=args.scope_confirmation,
            source_evidence=source,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {
            "status": "BLOCKED",
            "reason": f"unreadable input: {type(exc).__name__}",
            "analysis_authorization_issued": False,
        }
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result.get("status") == "SOURCE_REVIEW_GATES_PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
