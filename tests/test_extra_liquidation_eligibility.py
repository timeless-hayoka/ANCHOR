"""Deterministic oracle-triage negative and arithmetic controls."""
from extra_liquidation_eligibility import TokenObservation, evaluate_candidate

A = "0x" + "11" * 20
B = "0x" + "22" * 20
ORACLE = "0x" + "33" * 20
BLOCK = 120_000_000


def obs(token, amount, *, price=10**18, decimals=6, block=BLOCK, verified=True):
    return TokenObservation(token, amount, decimals, price, block, ORACLE, "snapshot", verified)


def evaluate(collateral, debt, **kwargs):
    return evaluate_candidate(
        chain_id=10, block=BLOCK, vault_id=3, position_id=16,
        threshold_bps=8333, collateral=collateral, debt=debt, **kwargs
    )


def test_same_block_risk_ratio_never_authorizes_liquidation():
    result = evaluate((obs(A, 100_000_000),), (obs(B, 90_000_000),))
    assert result.status == "AT_RISK_UNCONFIRMED"
    assert result.ratio_bps_floor == 9000
    assert result.collateral_value_e18 == 100 * 10**18
    assert result.debt_value_e18 == 90 * 10**18


def test_source_flags_still_do_not_pretend_simulation_proved_liquidation():
    result = evaluate((obs(A, 100_000_000),), (obs(B, 90_000_000),),
                      implementation_predicate_verified=True,
                      price_divergence_check_verified=True,
                      liquidity_valuation_verified=True)
    assert result.status == "AT_RISK_UNCONFIRMED"


def test_floor_threshold_boundary_is_not_risk():
    result = evaluate((obs(A, 100_000_000),), (obs(B, 83_330_000),))
    assert result.status == "HEALTHY_UNCONFIRMED"
    assert result.ratio_bps_floor == 8333


def test_unverified_stale_zero_or_invalid_price_are_unknown():
    bad_debts = (
        obs(B, 90_000_000, verified=False),
        obs(B, 90_000_000, block=BLOCK - 1),
        obs(B, 90_000_000, price=0),
        obs(B, -1),
    )
    for debt in bad_debts:
        assert evaluate((obs(A, 100_000_000),), (debt,)).status == "UNKNOWN"


def test_missing_inputs_and_duplicate_assets_are_unknown():
    assert evaluate((), (obs(B, 9),)).status == "UNKNOWN"
    assert evaluate((obs(A, 0),), (obs(B, 9),)).status == "UNKNOWN"
    assert evaluate((obs(A, 100), obs(A, 100)), (obs(B, 9),)).status == "UNKNOWN"


def test_cannot_use_other_chain_or_position_without_provenance():
    result = evaluate_candidate(
        chain_id=8453, block=BLOCK, vault_id=3, position_id=16,
        threshold_bps=8333, collateral=(obs(A, 100),), debt=(obs(B, 90),)
    )
    assert result.status == "UNKNOWN"


def test_mixed_token_decimals_and_prices():
    # $300 collateral in 18-decimal units; $200 debt in 6-decimal units.
    collateral = (obs(A, 2 * 10**18, price=150 * 10**18, decimals=18),)
    debt = (obs(B, 200 * 10**6),)
    result = evaluate(collateral, debt)
    assert result.ratio_bps_floor == 6666
    assert result.status == "HEALTHY_UNCONFIRMED"


def test_invalid_data_types_fail_closed():
    bad = TokenObservation(A, 100, 6, 10**18, BLOCK, ORACLE, None, True)
    assert evaluate((bad,), (obs(B, 100),)).status == "UNKNOWN"
    assert evaluate((obs(A, 100),), (object(),)).status == "UNKNOWN"
