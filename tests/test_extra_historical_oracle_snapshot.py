"""Independent arithmetic checks on read-only historical onchain evidence.

The proportional-reserve computation is a diagnostic, NOT an oracle valuation
or a claim that position #16 was actually liquidatable.
"""
import json
from pathlib import Path

SNAPSHOT = (
    Path(__file__).resolve().parents[1] /
    "evidence/extra_finance_op_120000000_vault3_position16_oracle_snapshot.json"
)


def snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_archived_evidence_has_immutable_block_and_no_proof_promotion():
    data = snapshot()
    assert data["provenance"]["chain_id"] == 10
    assert data["provenance"]["block_number"] == 120_000_000
    assert data["provenance"]["transactions_broadcast"] is False
    assert data["provenance"]["storage_overrides"] is False
    assert data["verification"]["liquidation_eligible"] == "UNKNOWN"
    assert data["verification"]["liquidation_replay_attempted"] is False
    assert data["verification"]["finding"] == "NONE"


def test_historical_gauge_custody_matches_vault_bookkeeping():
    state = snapshot()["historical_state"]
    assert int(state["vault_total_lp_raw"]) == int(state["gauge_vault_staked_lp_raw"])
    assert int(state["vault_direct_lp_balance_raw"]) == 0
    assert int(state["vault_total_lp_raw"]) > int(state["position_lp_raw"]) > 0


def test_illustrative_proportional_lp_underlying_uses_integer_floors():
    state = snapshot()["historical_state"]
    lp = int(state["position_lp_raw"])
    total = int(state["pair_total_lp_supply_raw"])
    reserve0 = int(state["reserves_raw"]["token0"])
    reserve1 = int(state["reserves_raw"]["token1"])
    # These are proportional AMM redemption operands, NOT a verified
    # source-matched vault valuation nor a TWAP liquidation price.
    amount0 = lp * reserve0 // total
    amount1 = lp * reserve1 // total
    assert amount0 == 25_315_513_568_127_227_154
    assert amount1 == 63_502_558
    assert state["token0_decimals"] == 18
    assert state["token1_decimals"] == 6


def test_chainlink_raw_return_is_not_assumed_usd_or_liquidation_price():
    data = snapshot()
    state = data["historical_state"]
    assert state["chainlink_get_price_available"] is True
    assert int(state["chainlink_get_price_raw"]) > 0
    assert data["verification"]["chainlink_quote_direction_and_scale_verified"] is False
    assert data["verification"]["source_matched_twap_valuation_verified"] is False
    assert data["verification"]["liquidation_predicate_verified"] is False


def test_historical_position_state_is_fingerprinted():
    state = snapshot()["historical_state"]
    assert state["position_abi_hash"] == (
        "0xfdbf41f35b21cdd886cb461a53f4ed745332d99bb3f9deecc46585d1dac0df53"
    )
    assert state["liquidation_with_twap"] is True
    assert state["liquidation_debt_ratio_raw"] == 8334
    assert state["permissionless_liquidation"] is False
