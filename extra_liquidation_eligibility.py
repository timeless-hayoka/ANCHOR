"""Fail-closed oracle-aware liquidation *triage* for historical Extra Finance.

This calculator intentionally does not certify the deployed vault's liquidation
predicate. The historical manager delegates execution to the vault, which may
use TWAP, spot, price-deviation and fee/callback logic beyond a debt ratio.
It produces a numeric *candidate*, never an executable-liquidation approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

MAX_TOKEN_DECIMALS = 36
MAX_AMOUNT = 2**256 - 1
MAX_PRICE = 2**256 - 1
BPS = 10_000

@dataclass(frozen=True)
class TokenObservation:
    token: str
    amount: int
    decimals: int
    price_e18: int
    price_block: int
    oracle_address: str
    oracle_method: str
    oracle_verified: bool = False

@dataclass(frozen=True)
class Triage:
    status: str
    debt_value_e18: int | None
    collateral_value_e18: int | None
    ratio_bps_floor: int | None
    reason: str


def _valid_token(item: TokenObservation, block: int) -> bool:
    return (
        isinstance(item.token, str)
        and item.token.startswith("0x")
        and len(item.token) == 42
        and isinstance(item.oracle_address, str)
        and item.oracle_address.startswith("0x")
        and len(item.oracle_address) == 42
        and bool(item.oracle_method.strip())
        and type(item.amount) is int
        and 0 <= item.amount <= MAX_AMOUNT
        and type(item.decimals) is int
        and 0 <= item.decimals <= MAX_TOKEN_DECIMALS
        and type(item.price_e18) is int
        and 0 < item.price_e18 <= MAX_PRICE
        and type(item.price_block) is int
        and item.price_block == block
        and item.oracle_verified is True
    )


def evaluate_candidate(
    *,
    chain_id: int,
    block: int,
    vault_id: int,
    position_id: int,
    threshold_bps: int,
    collateral: tuple[TokenObservation, ...],
    debt: tuple[TokenObservation, ...],
    implementation_predicate_verified: bool = False,
    price_divergence_check_verified: bool = False,
    liquidity_valuation_verified: bool = False,
) -> Triage:
    """Compute an indicative USD-denominated debt ratio with integer floors.

    Inputs are caller-supplied observations: a true boolean here is *not*
    proof of provenance. The oracle path must be verified independently.
    In particular, AMM LP position value cannot be obtained merely by summing
    wallet balances. Even a numerical breach remains a triage signal.
    """
    unknown = lambda reason: Triage("UNKNOWN", None, None, None, reason)
    if (chain_id != 10 or type(block) is not int or block <= 0
            or type(vault_id) is not int or vault_id <= 0
            or type(position_id) is not int or position_id <= 0):
        return unknown("missing or unsupported historical position provenance")
    if type(threshold_bps) is not int or not 0 < threshold_bps <= BPS:
        return unknown("missing or invalid deployed liquidation threshold")
    if not collateral or not debt:
        return unknown("missing collateral or debt observations")
    if not all(_valid_token(t, block) for t in (*collateral, *debt)):
        return unknown("missing, unverified, stale or invalid same-block oracle evidence")

    # Distinct token observations are required within each side. A duplicated
    # token could otherwise silently double-count its value.
    for side in (collateral, debt):
        addresses = [t.token.lower() for t in side]
        if len(addresses) != len(set(addresses)):
            return unknown("duplicate token observations")

    value = lambda items: sum(
        (t.amount * t.price_e18) // 10**t.decimals for t in items
    )
    collateral_value = value(collateral)
    debt_value = value(debt)
    if collateral_value <= 0:
        return unknown("zero or unvalued position collateral")
    ratio = debt_value * BPS // collateral_value

    # External inputs can at most provide a risk candidate. An actual
    # liquidation must be proven separately on the deployed vault.
    if not (implementation_predicate_verified
            and price_divergence_check_verified
            and liquidity_valuation_verified):
        status = "AT_RISK_UNCONFIRMED" if debt_value * BPS > collateral_value * threshold_bps else "HEALTHY_UNCONFIRMED"
        return Triage(status, debt_value, collateral_value, ratio,
                      "indicative ratio only; deployed vault predicate, AMM LP valuation or price-protection evidence incomplete")
    status = "AT_RISK_UNCONFIRMED" if debt_value * BPS > collateral_value * threshold_bps else "HEALTHY_UNCONFIRMED"
    return Triage(status, debt_value, collateral_value, ratio,
                  "inputs passed arithmetic checks; independent deployed-fork liquidation proof still required")
