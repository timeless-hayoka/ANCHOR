"""Offline tests of the Sourcify 0.8.18 compiler-input gate."""
import importlib.util
from pathlib import Path

import pytest

p = Path(__file__).resolve().parents[1] / "scripts/extra_verified_source_compile.py"
s = importlib.util.spec_from_file_location("verified_source_compiler", p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

ADDR = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
SNAPSHOT = {
    "chainId": "10", "address": ADDR, "runtimeMatch": "match",
    "compilation": {"language": "Solidity", "compilerVersion": "0.8.18+commit.87f61d96"},
    "runtimeBytecode": {"recompiledBytecode": "0x6000"},
    "stdJsonInput": {
        "language": "Solidity",
        "sources": {"contracts/lendingpool/LendingPool.sol": {"content": "contract LendingPool{}"}},
        "settings": {"optimizer": {"enabled": True, "runs": 200}},
    },
}


def test_prepare_valid_compiler_input_without_mutating_input():
    inp, meta = m.prepare_input(SNAPSHOT)
    assert inp["settings"]["outputSelection"]["contracts/lendingpool/LendingPool.sol"]["LendingPool"] == ["evm.deployedBytecode.object"]
    assert meta["compiler_version"].startswith("0.8.18")
    assert "outputSelection" not in SNAPSHOT["stdJsonInput"]["settings"]


@pytest.mark.parametrize("changes", [
    {"chainId": "8453"},
    {"address": "0x" + "1" * 40},
    {"runtimeMatch": None},
    {"compilation": {"language": "Solidity", "compilerVersion": "0.8.20"}},
    {"stdJsonInput": {}},
])
def test_unverified_or_wrong_build_is_rejected(changes):
    with pytest.raises(ValueError):
        m.prepare_input({**SNAPSHOT, **changes})


def test_compile_output_does_not_claim_onchain_equivalence():
    _, meta = m.prepare_input(SNAPSHOT)
    compiled = {"contracts": {
        "contracts/lendingpool/LendingPool.sol": {
            "LendingPool": {"evm": {"deployedBytecode": {"object": "6000"}}}
        }
    }}
    report = m.compare_compilation(compiled, meta)
    assert report["state"] == "PROVIDER_BUILD_COMPILED"
    assert report["compiler_equals_provider_recompiled"] is True
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"
    assert report["independent_rpc_check"] == "NOT_PERFORMED"


def test_compiler_errors_fail_closed():
    _, meta = m.prepare_input(SNAPSHOT)
    result = m.compare_compilation(
        {"errors": [{"severity": "error", "message": "parser failure"}]}, meta
    )
    assert result["state"] == "COMPILE_NOT_PROVEN"
    assert "parser failure" in result["compiler_errors_first_3"][0]
