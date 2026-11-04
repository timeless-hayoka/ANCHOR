"""Historic Extra Finance registry evidence checks, without source promotion."""
from __future__ import annotations

import json
from pathlib import Path

EVIDENCE = (
    Path(__file__).resolve().parents[1]
    / "evidence/extra_finance_op_120000000_vault3_logic_identity.json"
)


def _snapshot() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_fork_provenance_and_vault_identity_are_pinned():
    data = _snapshot()
    provenance = data["provenance"]
    assert provenance["chain_id"] == 10
    assert provenance["block_number"] == 120_000_000
    assert provenance["vault_id"] == 3
    assert provenance["archive_fork_only"]
    assert provenance["no_broadcast"]
    assert provenance["no_storage_override"]
    assert provenance["vault_runtime_codehash"] == (
        "0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480"
    )


def test_registry_entries_are_unique_and_versioned_correctly():
    data = _snapshot()
    entries = data["registry_observations"]
    assert len(entries) == 12
    keys = [int(entry["key"]) for entry in entries]
    assert len(keys) == len(set(keys))
    for entry in entries:
        expected_key = (
            (1 << 128) + entry["base_id"]
            if entry["version"] == 1
            else entry["base_id"]
        )
        assert int(entry["key"]) == expected_key
        assert entry["source_equivalence"] == "NOT_PROVEN"
        assert len(entry["codehash"]) == 66
        assert entry["code_size"] > 0

    by_id = {(e["version"], e["base_id"]): e for e in entries}
    assert by_id[(1, 1003)]["address"].lower() == (
        "0x512c21d420a5841a3c06636d5ee194a565a07d5c"
    )
    assert by_id[(None, 103)]["address"].lower() == (
        "0x5a583ccb69402d60bc360d691eedb8efda6fb7e5"
    )


def test_source_equivalence_and_liquidation_remain_unproven():
    snapshot = _snapshot()
    assert snapshot["probe_result"]["optional_implementation_getter"] == "UNAVAILABLE"
    assert snapshot["probe_result"]["exact_deployed_source"] == "UNVERIFIED"
    assert snapshot["probe_result"]["liquidation_eligibility"] == "UNKNOWN"
    assert snapshot["probe_result"]["liquidation_replay"] == "NOT_ATTEMPTED"
    assert snapshot["source_lookup"]["equivalence_conclusion"] == "UNKNOWN"
