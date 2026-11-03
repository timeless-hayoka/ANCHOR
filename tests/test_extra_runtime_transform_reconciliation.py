"""Tests for strict, transformation-aware runtime bytecode reconciliation."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "extra_runtime_transform_reconciliation",
    ROOT / "scripts" / "extra_runtime_transform_reconciliation.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
# Synthetic Solidity-style CBOR suffix containing one byte payload and a two-byte length.
BASE = bytes.fromhex("6001600055")
METADATA = bytes.fromhex("a10001")  # deliberately not used as a valid CBOR suffix
# Full metadata bytes: a1 00 01, then 0x0003 encoded payload length.
VALID_META = bytes.fromhex("a100010003")
ONCHAIN = BASE + VALID_META
RECOMPILED = BASE + bytes.fromhex("a100020003")
SHA = mod.hashlib.sha256(("0x" + ONCHAIN.hex()).encode("utf-8")).hexdigest()
RPC = {
    "state": "RPC_MATCHES_PROVIDER_ONCHAIN",
    "chain_id": "10",
    "address": ADDRESS,
    "rpc_onchain_sha256": SHA,
    "provider_onchain_sha256": SHA,
    "transaction_broadcast": False,
}
SNAPSHOT = {
    "chainId": "10",
    "address": ADDRESS,
    "runtimeMatch": "match",
    "runtimeBytecode": {
        "onchainBytecode": "0x" + ONCHAIN.hex(),
        "recompiledBytecode": "0x" + RECOMPILED.hex(),
        "transformations": [{
            "id": "1", "type": "replace", "reason": "cborAuxdata", "offset": len(BASE)
        }],
        "transformationValues": {"cborAuxdata": {"1": "0x" + VALID_META.hex()}},
        "cborAuxdata": {"1": {"offset": len(BASE), "value": "0x" + VALID_META.hex()}},
    },
}


def test_declared_metadata_only_difference_reconciles_with_independent_rpc():
    report = mod.examine(SNAPSHOT, RPC)
    assert report["state"] == "DECLARED_TRANSFORMS_RECONCILED"
    assert report["rpc_attestation"] == "RPC_MATCHES_PROVIDER_ONCHAIN"
    assert report["unexplained_byte_count"] == 0
    assert report["changed_byte_count"] == 1
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"
    assert report["finding"] == "NONE"


def test_planted_opcode_change_fails_outside_metadata_region():
    changed = dict(SNAPSHOT)
    runtime = dict(SNAPSHOT["runtimeBytecode"])
    changed["runtimeBytecode"] = runtime
    runtime["onchainBytecode"] = "0x" + (bytes.fromhex("6002600055") + VALID_META).hex()
    result = mod.examine(changed)
    assert result["state"] == "NOT_RECONCILED"
    assert 1 in result["first_unexplained_offsets"]


def test_missing_or_forged_transformation_values_fail_closed():
    for runtime_change in (
        {"transformations": []},
        {"transformationValues": {"cborAuxdata": {"1": "0xa100010002"}}},
        {"transformations": [{"id": "1", "type": "replace", "reason": "cborAuxdata", "offset": 0}]},
        {"transformations": [{"id": "1", "type": "replace", "reason": "cborAuxdata", "offset": 999}]},
        {"transformations": [{"id": "1", "type": "insert", "reason": "cborAuxdata", "offset": 5}]},
        {"transformations": [
            {"id": "1", "type": "replace", "reason": "cborAuxdata", "offset": 5},
            {"id": "1", "type": "replace", "reason": "cborAuxdata", "offset": 5},
        ]},
    ):
        snap = {**SNAPSHOT, "runtimeBytecode": {**SNAPSHOT["runtimeBytecode"], **runtime_change}}
        assert mod.examine(snap)["state"] == "NOT_RECONCILED", runtime_change


def test_fake_immutable_mask_cannot_hide_opcode_tampering():
    # A forged transformation payload must agree with Solidity's immutableReferences.
    original = bytes.fromhex("60016000")
    compiled = original + bytes(32) + bytes.fromhex("55")
    altered = original + bytes([7] * 32) + bytes.fromhex("55")
    malicious = {
        "chainId": "10", "address": ADDRESS, "runtimeMatch": "match",
        "runtimeBytecode": {
            "onchainBytecode": "0x" + altered.hex(),
            "recompiledBytecode": "0x" + compiled.hex(),
            "transformations": [{"id": "123", "type": "replace", "reason": "immutable", "offset": 4}],
            "transformationValues": {"immutables": {"123": "0x" + bytes([7] * 32).hex()}},
            "immutableReferences": {},
        },
    }
    result = mod.examine(malicious)
    assert result["state"] == "NOT_RECONCILED"
    assert "compiler reference map" in result["reason"]
    malicious["runtimeBytecode"]["immutableReferences"] = {
        "123": [{"start": 4, "length": 32}],
    }
    result = mod.examine(malicious)
    assert result["state"] == "DECLARED_TRANSFORMS_RECONCILED"
    assert result["full_deployment_equivalence"] == "NOT_PROVEN"


def test_wrong_chain_or_rpc_digest_blocks():
    assert mod.examine({**SNAPSHOT, "chainId": "8453"}, RPC)["state"] == "NOT_RECONCILED"
    assert mod.examine(SNAPSHOT, {**RPC, "rpc_onchain_sha256": "1" * 64})["state"] == "NOT_RECONCILED"
    assert mod.examine(SNAPSHOT, {**RPC, "transaction_broadcast": True})["state"] == "NOT_RECONCILED"


def test_unexplained_length_mismatch_blocks():
    runtime = {**SNAPSHOT["runtimeBytecode"], "recompiledBytecode": "0x" + RECOMPILED[:-1].hex()}
    assert mod.examine({**SNAPSHOT, "runtimeBytecode": runtime})["state"] == "NOT_RECONCILED"


def test_equal_provider_bytecode_does_not_claim_live_equivalence_without_rpc():
    rt = {**SNAPSHOT["runtimeBytecode"], "recompiledBytecode": "0x" + ONCHAIN.hex()}
    report = mod.examine({**SNAPSHOT, "runtimeBytecode": rt})
    assert report["state"] == "BYTE_IDENTICAL_PROVIDER_RUNTIME"
    assert report["rpc_attestation"] == "NOT_PROVIDED"
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"
