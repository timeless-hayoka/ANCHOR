"""Offline negative controls for historical evidence promotion gates."""
import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[1] / "scripts/extra_historical_evidence_gates.py"
spec = importlib.util.spec_from_file_location("historical_gates", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HASH = "0x" + "a" * 64
SOURCE = dict(observed_runtime_hash=HASH, compiled_runtime_hash=HASH,
              compiler_version="0.8.19", compiler_settings={"optimizer": True},
              linked_libraries={}, immutable_references={},
              constructor_immutables_verified=True)
EVIDENCE = {"provenance": {"chain_id": 10, "read_only": True,
                           "broadcast": False, "storage_overrides": False}}
REPLAY = dict(evidence=EVIDENCE, trace={"status": "AVAILABLE",
               "summary": {"truncated": False, "nodes": [{"type": "CALL"}]}},
              registry_at_execution={"101": "0x" + "1" * 40},
              observed_registry={"101": "0x" + "1" * 40},
              source_matched=True, authentic_eligibility_proven=True)


def test_exact_source_evidence_control():
    gate.require_source_equivalence(**SOURCE)


@pytest.mark.parametrize("change", [
    {"compiled_runtime_hash": "0x" + "b" * 64},
    {"compiler_version": ""},
    {"compiler_settings": {}},
    {"linked_libraries": {"L": "unknown"}},
    {"constructor_immutables_verified": False},
])
def test_source_evidence_negative_controls(change):
    with pytest.raises(gate.EvidenceGateError):
        gate.require_source_equivalence(**(SOURCE | change))


def test_complete_replay_control():
    gate.require_liquidation_replay(**REPLAY)


@pytest.mark.parametrize("change", [
    {"trace": {"status": "UNAVAILABLE"}},
    {"trace": {"status": "AVAILABLE", "summary": {"truncated": True, "nodes": []}}},
    {"observed_registry": {"101": "0x" + "2" * 40}},
    {"source_matched": False},
    {"authentic_eligibility_proven": False},
    {"evidence": {"provenance": {"chain_id": 1, "read_only": True,
                                  "broadcast": False, "storage_overrides": False}}},
])
def test_replay_negative_controls(change):
    with pytest.raises(gate.EvidenceGateError):
        gate.require_liquidation_replay(**(REPLAY | change))
