"""Synthetic controls for mapping deployed runtime immutable values to AST IDs."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "extra_verified_runtime_fixture",
    ROOT / "scripts" / "extra_verified_runtime_fixture.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REGISTRY = bytes.fromhex("11" * 20)
OTHER = bytes.fromhex("22" * 20)
IMM_REG = bytes(12) + REGISTRY
IMM_OTHER = bytes(12) + OTHER
INTRO = bytes.fromhex("6001")
CBOR_DEPLOYED = bytes.fromhex("a100010003")
CBOR_COMPILED = bytes.fromhex("a100020003")
ONCHAIN = INTRO + IMM_REG + IMM_OTHER + CBOR_DEPLOYED
RECOMPILED = INTRO + bytes(64) + CBOR_COMPILED
SHA = __import__("hashlib").sha256(("0x" + ONCHAIN.hex()).encode()).hexdigest()
ADDR = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
RPC = {
    "state": "RPC_MATCHES_PROVIDER_ONCHAIN", "chain_id": "10",
    "address": ADDR, "rpc_onchain_sha256": SHA,
    "provider_onchain_sha256": SHA, "transaction_broadcast": False,
}
SNAP = {
    "chainId": "10", "address": ADDR, "runtimeMatch": "match",
    "sources": {"contracts/lendingpool/LendingPool.sol": {
        "content": "contract LendingPool { address public immutable addressRegistry; }",
    }},
    "runtimeBytecode": {
        "onchainBytecode": "0x" + ONCHAIN.hex(),
        "recompiledBytecode": "0x" + RECOMPILED.hex(),
        "transformations": [
            {"type": "replace", "reason": "immutable", "id": "100", "offset": 2},
            {"type": "replace", "reason": "immutable", "id": "200", "offset": 34},
            {"type": "replace", "reason": "cborAuxdata", "id": "1", "offset": 66},
        ],
        "transformationValues": {
            "immutables": {"100": "0x" + IMM_REG.hex(), "200": "0x" + IMM_OTHER.hex()},
            "cborAuxdata": {"1": "0x" + CBOR_DEPLOYED.hex()},
        },
        "immutableReferences": {
            "100": [{"start": 2, "length": 32}],
            "200": [{"start": 34, "length": 32}],
        },
        "cborAuxdata": {"1": {"offset": 66, "value": "0x" + CBOR_COMPILED.hex()}},
    },
}
AST = {
    "nodeType": "SourceUnit", "nodes": [
        {"nodeType": "VariableDeclaration", "id": 100, "name": "addressRegistry",
         "mutability": "immutable", "stateVariable": True},
        {"nodeType": "VariableDeclaration", "id": 200, "name": "other",
         "mutability": "immutable", "stateVariable": True},
    ],
}


def test_registry_ast_id_selected_among_two_immutables():
    report = mod.fixture(SNAP, RPC, compiled_ast=AST)
    assert report["registry_address"] == "0x" + REGISTRY.hex()
    assert report["runtime_hex"] == "0x" + ONCHAIN.hex()
    assert report["evidence_class"] == "LOCAL_EVM_RUNTIME_SMOKE_ONLY"


def test_forged_ast_id_and_missing_source_fail_closed():
    bogus = {
        "nodeType": "SourceUnit", "nodes": [{
            "nodeType": "VariableDeclaration", "id": 333, "name": "addressRegistry",
            "mutability": "immutable", "stateVariable": True,
        }],
    }
    with pytest.raises(ValueError, match="AST id"):
        mod.fixture(SNAP, RPC, compiled_ast=bogus)
    broken = {**SNAP, "sources": {}}
    with pytest.raises(ValueError, match="expected immutable"):
        mod.fixture(broken, RPC, compiled_ast=AST)


def test_wrong_rpc_digest_never_generates_fixture():
    with pytest.raises(ValueError, match="not reconciled"):
        mod.fixture(SNAP, {**RPC, "rpc_onchain_sha256": "f" * 64}, compiled_ast=AST)
