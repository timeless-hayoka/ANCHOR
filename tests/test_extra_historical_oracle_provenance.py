"""Source safeguards for the archive-only liquidation dependency probe."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests/extra_historical_fork/AnchorExtraHistoricalOracleProvenance.t.sol"
WORKFLOW = ROOT / ".github/workflows/extra-finance-historical-oracle-provenance.yml"


def test_provenance_probe_is_pinned_to_real_state_without_mutations():
    text = PROBE.read_text(encoding="utf-8")
    assert "TARGET_BLOCK = 120000000" in text
    assert "block.chainid == 10 && block.number == TARGET_BLOCK" in text
    assert "IAnchorHistoricVaultFactory(factory).vaults(VAULT_ID)" in text
    assert "VAULT_RUNTIME_CODEHASH" in text
    assert "PAIR_RUNTIME_CODEHASH" in text
    assert "getVaultState()" in text
    assert "getVaultPosition(uint256,uint256)" in text
    assert "getReserves()" in text
    assert "PAIR_TOTAL_LP_SUPPLY_RAW" in text
    assert "POSITION_DEBT1_RAW" in text
    assert "GAUGE_STAKED_LP_BALANCE_RAW" in text
    assert "VAULT_TOTAL_LP_SHARES_RAW" in text
    assert "POSITION_LP_SHARES_RAW" in text
    assert "REGISTERED_CHAINLINK_ORACLE" in text
    assert "CHAINLINK_GETPRICE_RAW" in text
    assert "ORACLE_PREDICATE_UNVERIFIED" in text
    assert "LIQUIDATION_ELIGIBILITY_UNKNOWN" in text
    for forbidden in (
        "vm.store(", "vm.prank(", "deal(", "liquidateVaultPositionPartially(",
        "startBroadcast(", "broadcast(", "mockCall("
    ):
        assert forbidden not in text


def test_workflow_separates_compile_from_opt_in_archive_requests():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "forge build --root .extra-oracle-probe" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "github.head_ref == 'research/extra-historical-provenance-run-20261104'" in workflow
    assert "max-parallel" not in workflow  # no parallel historical matrix
    assert "cancel-in-progress: false" in workflow
    assert "--fork-block-number 120000000" in workflow
    assert '"oracle_eligibility":"UNKNOWN"' in workflow
    assert "--broadcast" not in workflow
