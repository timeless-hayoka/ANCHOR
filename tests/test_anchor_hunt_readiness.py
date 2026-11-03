"""Readiness gate acceptance tests: plausible artifacts do not grant permission."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anchor_hunt_readiness", ROOT / "scripts/anchor_hunt_readiness.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

REF = "a66e925d78ee5c990eb2bafa5009cebcbeafe42d"
TARGET = "ExtraFi/extra-contracts"
ADDR = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
DISCOVERY = {"candidates": [{"full_name": TARGET, "scan_status": "complete", "priority_score": 100}]}
SOURCE = {
    "chain_id": "10",
    "address": ADDR,
    "status": "PINNED_SOURCE_MATCH",
    "reported_runtime_match": "exact_match",
    "matched_source_paths": ["contracts/lendingpool/LendingPool.sol"],
    "source_sha256": "f" * 64,
}


def check(tmp_path: Path, **changes):
    arguments = {
        "target_id": TARGET,
        "target_ref": REF,
        "chain_id": "10",
        "contract_address": ADDR,
        "anchor_root": tmp_path,
        "discovery": DISCOVERY,
        "source_evidence": SOURCE,
        "scope_confirmation": None,
    }
    arguments.update(changes)
    return gate.assess(**arguments)


def approval(tmp_path: Path) -> Path:
    evidence = tmp_path / "policy.md"
    evidence.write_text("Synthetic lab authorization fixture only.", encoding="utf-8")
    confirmation = tmp_path / "confirmation.md"
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    reviewed = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    confirmation.write_text(
        "---\n"
        "schema_version: 1.0\n"
        f"target_id: {TARGET}\n"
        f"target_repo_url: https://github.com/{TARGET}\n"
        f"target_ref: {REF}\n"
        "scope_policy_url: https://example.com/scope\n"
        "permitted_actions:\n  - analysis\n"
        "prohibited_actions:\n  - mainnet-testing\n"
        "disclosure_channel: private-lab\n"
        "reviewer_decision: authorized\n"
        f"reviewed_at: {reviewed}\n"
        "identity_status: verified_repo\n"
        f"expires_at: {expires}\n"
        "evidence_url: https://example.com/synthetic-policy\n"
        "evidence_path: policy.md\n"
        "---\n",
        encoding="utf-8",
    )
    return confirmation


def test_default_blocks_even_high_score(tmp_path: Path):
    result = check(tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["checks"]["discovery"]["state"] == "PASS"
    assert result["checks"]["scope"]["state"] == "BLOCKED"
    assert result["analysis_authorization_issued"] is False


def test_synthetic_scope_and_exact_file_remain_not_deployment_equivalent(tmp_path: Path):
    result = check(tmp_path, scope_confirmation=approval(tmp_path))
    assert result["status"] == "SOURCE_REVIEW_GATES_PASSED"
    assert result["checks"]["scope"]["state"] == "PASS"
    assert result["checks"]["source_file"]["state"] == "PASS"
    assert result["full_deployment_equivalence"] == "NOT_PROVEN"
    assert result["foundry_reproduction"] == "NOT_EVALUATED"
    assert result["analysis_authorization_issued"] is False


def test_source_mismatch_and_nonexact_runtime_fail_closed(tmp_path: Path):
    confirmation = approval(tmp_path)
    for changed in (
        {"status": "NOT_VERIFIED"},
        {"reported_runtime_match": "match"},
        {"chain_id": "8453"},
        {"address": "0x" + "1" * 40},
        {"matched_source_paths": []},
        {"source_sha256": ""},
        {"matched_source_paths": "contracts/lendingpool/LendingPool.sol"},
    ):
        result = check(tmp_path, scope_confirmation=confirmation, source_evidence={**SOURCE, **changed})
        assert result["status"] == "BLOCKED", changed
        assert result["checks"]["source_file"]["state"] == "BLOCKED"


def test_target_ref_and_incomplete_scan_block(tmp_path: Path):
    confirmation = approval(tmp_path)
    for changed in (
        {"target_ref": "main"},
        {"target_ref": "0" * 40},
        {"discovery": {"candidates": [{"full_name": TARGET, "scan_status": "incomplete"}]}},
        {"discovery": {"candidates": [{"full_name": TARGET, "scan_status": "complete", "scan_errors": ["timeout"]}]}},
    ):
        result = check(tmp_path, scope_confirmation=confirmation, **changed)
        assert result["status"] == "BLOCKED", changed


def test_cli_cannot_pass_without_evidence(tmp_path: Path, capsys):
    code = gate.main([
        "--target-id", TARGET, "--target-ref", REF,
        "--chain-id", "10", "--contract-address", ADDR,
        "--anchor-root", str(tmp_path),
    ])
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["status"] == "BLOCKED"
    assert report["analysis_authorization_issued"] is False
