"""Regression rules for read-only historical vault logic identity research."""
from pathlib import Path

PROBE = (Path(__file__).resolve().parents[1] /
         "tests/extra_historical_fork/AnchorExtraHistoricalLogicIdentity.t.sol")


def test_logic_identity_probe_is_pinned_and_fail_closed():
    source = PROBE.read_text(encoding="utf-8")
    assert "block.chainid == 10 && block.number == 120000000" in source
    assert "EXPECTED_VAULT_CODEHASH" in source
    assert 'require(vault.codehash == EXPECTED_VAULT_CODEHASH' in source
    assert "REGISTRY_LOOKUP_UNAVAILABLE_ID" in source
    assert "REGISTRY_UNSET_ID" in source
    assert "REGISTERED_CODE_HASH" in source
    assert "version << 128" in source
    assert "EXACT_DEPLOYED_SOURCE_UNVERIFIED" in source
    assert "LIQUIDATION_ELIGIBILITY_UNKNOWN" in source
    for forbidden in ("vm.store(", "vm.prank(", "deal(", "startBroadcast(", "liquidateVaultPositionPartially(", "mockCall("):
        assert forbidden not in source
