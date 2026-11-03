"""Deployment evidence to Trinity signal handoff acceptance tests.

No live-network calls, authorizations, reproduction or finding promotion.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anchor_trinity_handoff", ROOT / "scripts/anchor_trinity_handoff.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

TARGET = "ExtraFi/extra-contracts"
REF = "a66e925d78ee5c990eb2bafa5009cebcbeafe42d"
ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
SOURCE = {
    "chain_id": "10", "address": ADDRESS, "status": "NOT_VERIFIED",
    "reported_runtime_match": "match",
}
READINESS = {
    "target_id": TARGET,
    "target_ref": REF,
    "chain_id": "10",
    "contract_address": ADDRESS,
    "status": "BLOCKED",
    "analysis_authorization_issued": False,
    "full_deployment_equivalence": "NOT_PROVEN",
    "foundry_reproduction": "NOT_EVALUATED",
    "trinity_finding_status": "NOT_EVALUATED",
    "checks": {
        "identity": {"state": "PASS", "detail": "exact pinned source"},
        "discovery": {"state": "BLOCKED", "detail": "no candidate bundle"},
        "scope": {"state": "BLOCKED", "detail": "no reviewed grant"},
        "source_file": {"state": "BLOCKED", "detail": "verified source differs"},
    },
}


def test_realistic_blocked_extra_finance_source_creates_signal_only():
    result = bridge.prepare_handoff(READINESS, SOURCE)
    assert result["handoff_status"] == "BLOCKED_RESEARCH_SIGNAL"
    assert result["lead"]["state"] == "signal"
    assert result["lead"]["scope_status"] == "unknown"
    assert result["lead"]["evidence_refs"] == []
    assert result["finding"] == "NONE"
    assert result["authorization_grant_issued"] is False
    assert result["deployment_bytecode_equivalence"] == "NOT_PROVEN"
    assert len(result["provenance"]["readiness_sha256"]) == 64
    assert bridge.prepare_handoff(READINESS, SOURCE)["lead"]["lead_id"] == result["lead"]["lead_id"]


def test_even_positive_source_review_cannot_promote_trinity():
    ready = json.loads(json.dumps(READINESS))
    ready["status"] = "SOURCE_REVIEW_GATES_PASSED"
    for check in ready["checks"].values():
        check["state"] = "PASS"
    source = {
        **SOURCE, "status": "PINNED_SOURCE_MATCH",
        "reported_runtime_match": "exact_match",
    }
    report = bridge.prepare_handoff(ready, source)
    assert report["handoff_status"] == "SOURCE_REVIEW_ONLY"
    assert report["lead"]["state"] == "signal"
    assert report["lead"]["scope_status"] == "unknown"
    assert report["finding"] == "NONE"


@pytest.mark.parametrize("readiness,source", [
    ({**READINESS, "target_ref": "main"}, SOURCE),
    ({**READINESS, "contract_address": "0x" + "1" * 40}, SOURCE),
    ({**READINESS, "analysis_authorization_issued": True}, SOURCE),
    ({**READINESS, "foundry_reproduction": "REPRODUCED_REAL"}, SOURCE),
    ({**READINESS, "full_deployment_equivalence": "PROVEN"}, SOURCE),
    ({**READINESS, "status": "SOURCE_REVIEW_GATES_PASSED"}, SOURCE),
    ({**READINESS, "checks": {}}, SOURCE),
    (READINESS, {**SOURCE, "chain_id": "8453"}),
    (READINESS, {**SOURCE, "address": "0x" + "0" * 40}),
    (READINESS, {**SOURCE, "status": "fabricated"}),
])
def test_contradictions_fail_closed(readiness, source):
    with pytest.raises(ValueError):
        bridge.prepare_handoff(readiness, source)


def test_cannot_reuse_fake_source_pass():
    ready = json.loads(json.dumps(READINESS))
    ready["checks"]["source_file"] = {"state": "PASS", "detail": "claimed match"}
    with pytest.raises(ValueError, match="source check passes"):
        bridge.prepare_handoff(ready, SOURCE)


def test_build_evidence_is_recorded_without_promoting_lead():
    source = {
        **SOURCE,
        "verified_source_candidates": [{
            "path": "contracts/lendingpool/LendingPool.sol",
            "sha256": "a" * 64,
        }],
    }
    build = {
        "state": "PROVIDER_BUILD_COMPILED",
        "chain_id": "10", "address": ADDRESS,
        "source_sha256": "a" * 64,
        "compiler_equals_provider_recompiled": True,
    }
    result = bridge.prepare_handoff(READINESS, source, build)
    assert result["provenance"]["build_state"] == "PROVIDER_RECOMPILE_MATCH_SOURCE_LINKED"
    assert result["lead"]["state"] == "signal"
    assert result["finding"] == "NONE"
    assert result["deployment_bytecode_equivalence"] == "NOT_PROVEN"


def test_other_chain_or_wrong_source_build_cannot_be_handed_off():
    source = {
        **SOURCE,
        "verified_source_candidates": [{"sha256": "a" * 64}],
    }
    good = {
        "state": "PROVIDER_BUILD_COMPILED", "chain_id": "10", "address": ADDRESS,
        "source_sha256": "a" * 64, "compiler_equals_provider_recompiled": True,
    }
    for changed in ({"chain_id": "8453"}, {"address": "0x" + "2" * 40}, {"source_sha256": "b" * 64}):
        with pytest.raises(ValueError):
            bridge.prepare_handoff(READINESS, source, {**good, **changed})


def test_compiler_failure_remains_visible_but_not_promoted():
    result = bridge.prepare_handoff(READINESS, SOURCE, {"state": "COMPILE_NOT_PROVEN"})
    assert result["provenance"]["build_state"] == "COMPILE_NOT_PROVEN"
    assert result["lead"]["scope_status"] == "unknown"


def test_independent_rpc_provenance_does_not_promote_finding():
    digest = "a" * 64
    rpc = {
        "state": "RPC_MATCHES_PROVIDER_ONCHAIN", "chain_id": "10",
        "address": ADDRESS,
        "provider_onchain_sha256": digest, "rpc_onchain_sha256": digest,
        "full_deployment_equivalence": "NOT_PROVEN", "transaction_broadcast": False,
    }
    result = bridge.prepare_handoff(READINESS, SOURCE, rpc_evidence=rpc)
    assert result["provenance"]["rpc_state"] == "RPC_MATCHES_PROVIDER_ONCHAIN"
    assert result["lead"]["state"] == "signal"
    assert result["finding"] == "NONE"
    assert result["deployment_bytecode_equivalence"] == "NOT_PROVEN"


def test_fabricated_rpc_hash_and_mismatched_address_fail_closed():
    good = {
        "state": "RPC_MATCHES_PROVIDER_ONCHAIN", "chain_id": "10",
        "address": ADDRESS,
        "provider_onchain_sha256": "a" * 64,
        "rpc_onchain_sha256": "a" * 64,
        "full_deployment_equivalence": "NOT_PROVEN", "transaction_broadcast": False,
    }
    for changed in (
        {"address": "0x" + "1" * 40},
        {"rpc_onchain_sha256": "b" * 64},
        {"transaction_broadcast": True},
        {"full_deployment_equivalence": "PROVEN"},
    ):
        with pytest.raises(ValueError):
            bridge.prepare_handoff(READINESS, SOURCE, rpc_evidence={**good, **changed})


def test_existing_evidence_artifact_is_not_overwritten(tmp_path):
    output = tmp_path / "handoff.json"
    report = bridge.prepare_handoff(READINESS, SOURCE)
    bridge.write_new_file(output, report)
    old = output.read_bytes()
    with pytest.raises(FileExistsError):
        bridge.write_new_file(output, {"forged": True})
    assert output.read_bytes() == old
    assert not list(tmp_path.glob(".anchor-handoff-*"))


def test_cli_blocked_signal_is_successful_research_output(tmp_path, capsys):
    ready = tmp_path / "readiness.json"
    source = tmp_path / "source.json"
    output = tmp_path / "handoff.json"
    ready.write_text(json.dumps(READINESS))
    source.write_text(json.dumps(SOURCE))
    assert bridge.main([
        "--readiness", str(ready), "--source-evidence", str(source),
        "--output", str(output),
    ]) == 0
    assert json.loads(output.read_text())["lead"]["state"] == "signal"
    assert json.loads(capsys.readouterr().out)["handoff_status"] == "BLOCKED_RESEARCH_SIGNAL"


def test_cli_rejects_malformed_json_without_writing(tmp_path, capsys):
    ready = tmp_path / "bad.json"
    source = tmp_path / "source.json"
    output = tmp_path / "handoff.json"
    ready.write_text("{")
    source.write_text(json.dumps(SOURCE))
    assert bridge.main([
        "--readiness", str(ready), "--source-evidence", str(source),
        "--output", str(output),
    ]) == 2
    assert not output.exists()
    assert json.loads(capsys.readouterr().out)["lead_created"] is False
