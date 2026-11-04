"""Regressions against backward-projected Extra Finance registry identities."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "evidence" / (
    "extra_finance_2023_vs_2024_factory_registry_drift.json"
)


def _data():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_historical_factory_and_vault_bytecode_are_same_at_both_blocks():
    d = _data()
    assert d["provenance"]["chain_id"] == 10
    assert d["provenance"]["creation_block"] == 96268610
    assert d["provenance"]["study_block"] == 120000000
    assert d["factory"]["runtime_code_size_bytes"] == 2449
    assert d["vault"]["runtime_code_size_bytes"] == 13930
    assert d["factory"]["creation_equals_study"] is True
    assert d["vault"]["creation_equals_study"] is True
    assert d["vault"]["keccak256"] == (
        "0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480"
    )


def test_registry_identifiers_changed_since_deployment():
    d = _data()
    earlier, later = d["registry"]["creation"], d["registry"]["study"]
    assert earlier["101"] == "0x2c58ece45ac754b80fd39f5e7e67a4b0e91a1525"
    assert later["101"] == "0xdcf0f4a0fc44f33de35d8c80ad5d248dbf838943"
    assert earlier["103"] == "0x4f4940a87d63a290d43b6550911896ff7aee354c"
    assert earlier["103"] != later["103"]
    assert earlier["107"] is None
    assert later["107"] is not None
    for base in (1001, 1003):
        key = str((1 << 128) + base)
        assert earlier[key] is None
        assert later[key] is not None


def test_static_bytecode_clues_do_not_override_evidence_gates():
    d = _data()
    assert "0xf18efb45" in d["factory"]["push4_literals"]
    assert d["factory"]["opcode_counts"]["DELEGATECALL"] == 1
    assert d["vault"]["opcode_counts"]["DELEGATECALL"] == 7
    assert d["trace"]["status"] == "UNAVAILABLE"
    assert d["source_verification"]["source_equivalence"] == "UNKNOWN"
    assert d["source_verification"]["historical_creation_delegatecall_target"] == "UNVERIFIED"
    assert d["source_verification"]["historical_liquidation_dispatch"] == "UNVERIFIED"
    assert d["eligibility"] == "UNKNOWN"
    assert d["liquidation_replay"] == "NOT_ATTEMPTED"
    assert d["finding"] == "NONE"
    assert d["provenance"]["read_only"] is True
    assert d["provenance"]["broadcast"] is False
