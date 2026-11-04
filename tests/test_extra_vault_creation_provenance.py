"""Deterministic integrity checks on the historical vault #3 deployment input.

No ABI, logic version, or liquidation predicate is inferred from these bytes.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / (
    "evidence/extra_finance_vault3_creation_transaction_20230504.json"
)


def _data():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_explorer_deployment_record_and_creation_target():
    d = _data()
    assert d["chain_id"] == 10
    assert d["block_number"] == 96268610
    assert d["transaction_hash"] == (
        "0xbdd878d0e7cdf19d7a25013839ac5a9ff677b923a6a42c4c41eba2583b3d4459"
    )
    assert d["reported_created_contract"].lower() == (
        "0x5101081495d209a80f5dbb1c5ecd76fe137a9ee9"
    )
    assert d["reported_internal_create_type"] == "CREATE2"


def test_exact_abi_word_structure_without_historical_schema_claim():
    d = _data()
    calldata = bytes.fromhex(d["calldata"][2:])
    assert calldata[:4].hex() == d["selector"][2:] == "f18efb45"
    word_section = calldata[4:]
    assert len(word_section) % 32 == 0
    assert len(word_section) == 14 * 32
    words = [word_section[i:i+32] for i in range(0, len(word_section), 32)]
    assert [x.hex() for x in words] == d["raw_abi_words"]
    assert int.from_bytes(words[0], "big") == 32
    assert int.from_bytes(words[1], "big") == 384
    payload = word_section[64:]
    assert len(payload) == 384
    assert int.from_bytes(payload[:32], "big") == 32
    assert int.from_bytes(payload[32:64], "big") == int(
        "4200000000000000000000000000000000000042", 16
    )
    assert int.from_bytes(payload[64:96], "big") == int(
        "7f5c764cbc14f9669b88837ca1490cca17c31607", 16
    )


def test_cannot_decode_creation_payload_as_pinned_versioned_wrapper():
    d = _data()
    payload = bytes.fromhex(d["calldata"][10 + 128:])
    # A canonical abi.encode(uint16, bytes) has first-word uint16
    # and second-word dynamic offset within the encoded payload.
    first_word = int.from_bytes(payload[:32], "big")
    dynamic_offset = int.from_bytes(payload[32:64], "big")
    assert first_word == 32
    assert dynamic_offset > len(payload)
    # This check rejects using the *pinned reference wrapper as-is*;
    # it does not prove what the actual 2023 factory ABI expected.
    assert d["source_status"]["creation_version"] == "UNKNOWN"


def test_all_eligibility_and_source_gates_remain_fail_closed():
    d = _data()
    assert d["source_status"]["verified_source_equivalence"] is False
    assert d["source_status"]["historical_factory_abi"] == "UNKNOWN"
    assert d["source_status"]["factory_method_signature"] == "UNVERIFIED"
    assert d["result"]["vault_version"] == "UNKNOWN"
    assert d["result"]["position_eligibility"] == "UNKNOWN"
    assert d["result"]["liquidation_replay"] == "NOT_ATTEMPTED"
    assert d["result"]["bounty_finding"] == "NONE"
