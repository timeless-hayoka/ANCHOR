"""Offline evidence checks for provider-only deployment metadata."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "anchor_deployment_provenance", ROOT / "scripts/anchor_deployment_provenance.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
EXAMPLE = {
    "chainId": "10",
    "address": ADDRESS,
    "runtimeMatch": "match",
    "compilation": {
        "language": "Solidity",
        "name": "LendingPool",
        "compilerVersion": "v0.8.18+commit.87f61d96",
        "compilerSettings": {"optimizer": {"enabled": True, "runs": 200}},
    },
    "sources": {"contracts/lendingpool/LendingPool.sol": {"content": "contract LendingPool {}"}},
    "runtimeBytecode": {
        "onchainBytecode": "0x6000",
        "recompiledBytecode": "0x6001",
    },
    "proxyResolution": {"isProxy": True, "proxyType": "EIP1967Proxy", "implementations": [
        {"address": "0x" + "1" * 40},
    ]},
}


def test_provider_metadata_is_not_deployment_equivalence():
    report = mod.analyze(EXAMPLE)
    assert report["state"] == "PROVIDER_METADATA_RECORDED"
    assert report["runtime_match"] == "match"
    assert report["compiler"]["compiler_version"].startswith("v0.8.18")
    assert report["optimizer"] == {"enabled": True, "runs": 200}
    assert report["provider_runtime_bytecode"]["byte_identical_in_provider_response"] is False
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"
    assert report["independent_rpc_bytecode_check"] == "NOT_PERFORMED"
    assert report["verified_source_count"] == 1
    assert report["proxy"]["is_proxy"] is True
    assert "onchainBytecode" not in str(report)


def test_provider_equal_bytecodes_do_not_mark_independent_proof():
    report = mod.analyze({
        **EXAMPLE, "runtimeMatch": "exact_match",
        "runtimeBytecode": {
            "onchainBytecode": "0x6000", "recompiledBytecode": "0x6000",
        },
    })
    assert report["provider_runtime_bytecode"]["byte_identical_in_provider_response"] is True
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"
    assert report["independent_rpc_bytecode_check"] == "NOT_PERFORMED"


def test_wrong_deployment_and_unverified_runtime_fail_closed():
    for modified in (
        {"chainId": "8453"},
        {"address": "0x" + "2" * 40},
        {"runtimeMatch": "not_verified"},
    ):
        report = mod.analyze({**EXAMPLE, **modified})
        assert report["state"] == "NOT_VERIFIED"


def test_missing_compilation_and_malformed_bytecode_recorded():
    report = mod.analyze({
        **EXAMPLE, "compilation": None,
        "runtimeBytecode": {"onchainBytecode": "not hex", "recompiledBytecode": "0x6000"},
    })
    assert report["state"] == "PROVIDER_METADATA_RECORDED"
    assert report["compiler_status"] == "MISSING"
    assert report["provider_runtime_bytecode"]["state"] == "MISSING_OR_MALFORMED"
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"
