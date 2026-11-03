"""Mocked read-only Optimism chain bytecode attestation controls."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "scripts" / "extra_rpc_bytecode_attestation.py"
s = importlib.util.spec_from_file_location("extra_rpc_attest", p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
CODE = "0x6001600055"
SHA = hashlib.sha256(CODE.encode()).hexdigest()
PROVIDER = {
    "state": "PROVIDER_METADATA_RECORDED", "chain_id": "10", "address": ADDRESS,
    "provider_runtime_bytecode": {"onchain_sha256": SHA},
}


def mock_rpc(method, params):
    if method == "eth_chainId":
        assert params == []
        return "0xa"
    if method == "eth_blockNumber":
        assert params == []
        return "0x100"
    if method == "eth_getCode":
        assert params == [ADDRESS, "0x100"]
        return CODE
    raise AssertionError(method)


def test_independent_hash_agrees_but_full_parity_unproven():
    report = m.attestation(PROVIDER, rpc=mock_rpc)
    assert report["state"] == "RPC_MATCHES_PROVIDER_ONCHAIN"
    assert report["queried_block"] == "0x100"
    assert report["transaction_broadcast"] is False
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"


def test_planted_bytecode_change_is_detected():
    def altered(method, params):
        return "0x6002600055" if method == "eth_getCode" else mock_rpc(method, params)
    report = m.attestation(PROVIDER, rpc=altered)
    assert report["state"] == "RPC_PROVIDER_BYTECODE_MISMATCH"
    assert report["full_deployment_equivalence"] == "NOT_PROVEN"


def test_wrong_chain_and_malformed_code_fail_closed():
    def wrong_chain(method, params):
        return "0x2105" if method == "eth_chainId" else mock_rpc(method, params)
    assert m.attestation(PROVIDER, rpc=wrong_chain)["state"] == "NOT_ATTESTED"

    def missing_code(method, params):
        return "0x" if method == "eth_getCode" else mock_rpc(method, params)
    assert m.attestation(PROVIDER, rpc=missing_code)["state"] == "NOT_ATTESTED"


def test_provider_wrong_contract_is_refused_without_network_call():
    bad = {**PROVIDER, "address": "0x" + "1" * 40}
    def should_not_call(*args):
        raise AssertionError("network must not be called")
    assert m.attestation(bad, rpc=should_not_call)["state"] == "NOT_ATTESTED"
