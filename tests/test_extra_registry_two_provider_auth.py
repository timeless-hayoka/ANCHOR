"""Offline controls for two-provider, block-bound historical registry authentication."""
import importlib.util
import copy
import json
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "extra_registry_two_provider_auth", ROOT / "scripts/extra_registry_two_provider_auth.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
PINNED = json.loads((ROOT / "evidence/extra_finance_2023_vs_2024_factory_registry_drift.json").read_text())


def observation(label, block):
    return {"chain_id": 10, "block_number": block,
            "block_hash": "0x" + ("a" if label == "creation" else "b") * 64,
            "registry_address": mod.REGISTRY, "factory_address": mod.FACTORY,
            "vault_address": mod.VAULT,
            "runtime_sha256": {"factory": mod.EXPECTED_FACTORY_SHA256,
                               "vault": mod.EXPECTED_VAULT_SHA256,
                               "registry": "c" * 64},
            "registry_entries": copy.deepcopy(PINNED["registry"][label])}


def fake_observe(url, height):
    label = next(label for label, block in mod.BLOCKS.items() if block == height)
    return observation(label, height)


def test_two_matching_providers_accept_observations_without_promoting_exploit():
    with patch.object(mod, "observe", side_effect=fake_observe):
        result = mod.authenticate("https://a.invalid", "https://b.invalid", PINNED)
    assert result["status"] == "AUTHENTICATED_TWO_PROVIDER"
    assert result["source_equivalence"] == "UNKNOWN"
    assert result["liquidation_eligibility"] == "UNKNOWN"


@pytest.mark.parametrize("mutation", ["block_hash", "runtime_sha256", "registry_entries", "chain_id"])
def test_provider_disagreement_rejected(mutation):
    def disagree(url, height):
        label = next(label for label, block in mod.BLOCKS.items() if block == height)
        item = observation(label, height)
        if url == "https://b.invalid":
            if mutation == "block_hash":
                item["block_hash"] = "0x" + "f" * 64
            elif mutation == "runtime_sha256":
                item["runtime_sha256"]["registry"] = "f" * 64
            elif mutation == "registry_entries":
                item["registry_entries"]["101"] = None
            else:
                item["chain_id"] = 1
        return item
    with patch.object(mod, "observe", side_effect=disagree):
        with pytest.raises(mod.AuthenticationError):
            mod.authenticate("https://a.invalid", "https://b.invalid", PINNED)


def test_stale_pinned_registry_rejected():
    stale = json.loads(json.dumps(PINNED))
    stale["registry"]["creation"]["101"] = "0x" + "f" * 40
    with patch.object(mod, "observe", side_effect=fake_observe):
        with pytest.raises(mod.AuthenticationError):
            mod.authenticate("https://a.invalid", "https://b.invalid", stale)


@pytest.mark.parametrize("a,b", [
    ("http://a.invalid", "https://b.invalid"),
    ("https://same.invalid", "https://same.invalid"),
])
def test_requires_distinct_https_endpoints(a, b):
    with pytest.raises(mod.AuthenticationError):
        mod.authenticate(a, b, PINNED)


def test_wrong_chain_and_reorg_and_code_mismatch_rejected():
    block = 96268610
    registry_word = lambda key: "0x" + "00" * 32
    def fixture(url, method, params, request_id):
        if method == "eth_chainId":
            return "0xa"
        if method == "eth_getBlockByNumber":
            return {"number": hex(block), "hash": "0x" + "a" * 64}
        if method == "eth_getCode":
            return "0x6000"  # intentionally mismatches pinned bytecode
        if method == "eth_call":
            return registry_word(0)
        raise AssertionError(method)
    with patch.object(mod, "rpc", side_effect=fixture):
        with pytest.raises(mod.AuthenticationError, match="runtime differs"):
            mod.observe("https://a.invalid", block)


def test_historical_state_queries_use_canonical_block_hash():
    block_number = 96268610
    block_hash = "0x" + "a" * 64
    observed_refs = []
    def fixture(url, method, params, request_id):
        if method == "eth_chainId":
            return "0xa"
        if method == "eth_getBlockByNumber":
            return {"number": hex(block_number), "hash": block_hash}
        if method in ("eth_getCode", "eth_call"):
            observed_refs.append(params[-1])
            if method == "eth_getCode":
                return "0x6000"
            return "0x" + "00" * 32
        raise AssertionError(method)
    with patch.object(mod, "rpc", side_effect=fixture):
        with pytest.raises(mod.AuthenticationError, match="runtime differs"):
            mod.observe("https://a.invalid", block_number)
    assert observed_refs == [{"blockHash": block_hash, "requireCanonical": True}]


def test_provider_rejecting_canonical_hash_read_fails_closed():
    block_number = 96268610
    block_hash = "0x" + "a" * 64
    requests = []

    def fixture(url, method, params, request_id):
        requests.append((method, params))
        if method == "eth_chainId":
            return "0xa"
        if method == "eth_getBlockByNumber":
            return {"number": hex(block_number), "hash": block_hash}
        if method == "eth_getCode":
            assert params[1] == {"blockHash": block_hash, "requireCanonical": True}
            raise mod.AuthenticationError("provider does not support EIP-1898")
        raise AssertionError("unexpected fallback request")

    with patch.object(mod, "rpc", side_effect=fixture):
        with pytest.raises(mod.AuthenticationError, match="does not support"):
            mod.observe("https://a.invalid", block_number)
    assert [method for method, _ in requests] == [
        "eth_chainId", "eth_getBlockByNumber", "eth_getCode"
    ]
