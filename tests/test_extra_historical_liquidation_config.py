"""Regression checks for fail-closed historical liquidation-config discovery.

These tests protect the ABI field offsets and prevent a read-only scanner from
silently asserting liquidation eligibility without source-matched oracle data.
"""
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "tests/extra_historical_fork/AnchorExtraHistoricalPositionDiscovery.t.sol"
)


def test_liquidation_config_uses_deployed_getter_and_source_matched_offsets():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'abi.encodeWithSignature("getVault(uint256)", vaultId)' in source
    for operand in (
        "usesTwap := mload(add(raw, 288))",
        "maxPriceDiff := mload(add(raw, 384))",
        "liquidationDebtRatio := mload(add(raw, 416))",
    ):
        assert operand in source
    assert "raw.length < 13 * 32" in source
    assert "usesTwap > 1" in source
    assert "liquidationDebtRatio == 0" in source


def test_scanner_does_not_promote_unpriced_positions_to_eligible():
    source = SOURCE.read_text(encoding="utf-8")
    assert "VAULT_LIQUIDATION_ELIGIBILITY_UNKNOWN" in source
    assert "VAULT_CONFIG_UNAVAILABLE" in source
    assert "VAULT_CONFIG_ABI_HASH" in source
    assert "_inspectVaultLiquidationConfig(manager, vaultId);" in source
    assert "ELIGIBLE_FOR_LIQUIDATION" not in source
    # The discovery fixture must remain read-only; no production simulation
    # or direct storage changes belong in this scan.
    assert "manager.staticcall(" in source
    for forbidden in ("vm.store(", "vm.prank(", "liquidateVaultPositionPartially("):
        assert forbidden not in source
