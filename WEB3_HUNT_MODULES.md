# ANCHOR Web3 Hunt Modules

ANCHOR does not promote a Web3 claim because it looks plausible.

ANCHOR promotes a claim only when:

`signal -> hypothesis -> repro_attempted -> reproduced_real -> council_accepted -> report_ready`

## Evidence Gate

Never let Trinity say:

`This is a zero-day.`

until Forge can say:

`This reproduces.`

Use these confidence levels:

- `symbolic path found` -> `PRIORITY_REVIEW`
- `forge reproduction passed` -> `HIGH_CONFIDENCE`
- `real impact proven` -> `PRIORITY_ONE`

## Module Order

Implement in this order:

1. Invariant Testing
2. State-Difference Probing
3. Oracle Delay Mocking
4. Symbolic Path Mapping

Why this order:

- Invariant and state-difference tests create the cleanest Forge proofs.
- Oracle mocking is highly valuable for DeFi but still benefits from a strong repro gate first.
- Symbolic execution is powerful, but it produces more noise unless the reproduction layer is already disciplined.

## 1. Invariant Testing

Purpose:

`some truth should never break`

Use for:

- `totalAssets >= totalShares` value
- `sum(userBalances) <= contractBalance`
- pool reserves match accounting
- `totalSupply` only changes through mint or burn
- oracle price age stays below `maxDelay`

ANCHOR rule:

`invariant break -> forge reproduces sequence -> council reviews impact -> evidence agent accepts only with proof`

This should be one of ANCHOR's strongest Web3 engines.

## 2. State-Difference Probing

Purpose:

`expected balance/state delta` vs `actual balance/state delta`

Use for:

- withdrawals
- deposits
- swaps
- liquidations
- fee accounting
- share mint or burn logic

ANCHOR rule:

`if actual delta != expected delta: create claim, attach trace, send to council`

Council severity guide:

- High if value moves
- Medium if accounting desync only
- Low if harmless rounding

## 3. Oracle Delay Mocking

Purpose:

`what happens if price data is stale, manipulated, or delayed?`

Use for:

- lending protocols
- liquidations
- AMMs
- vault share pricing
- collateral valuation
- cross-chain price feeds

Forge should test:

- stale price
- zero price
- extreme price
- delayed update
- round mismatch
- negative or invalid answer if the oracle supports it

ANCHOR rule:

`bad oracle input -> protocol accepts it -> value-impacting action succeeds -> council reviews as high-risk`

## 4. Symbolic Path Mapping

Purpose:

Map dangerous paths without pretending they are findings.

Use for:

- unauthenticated withdraw
- selfdestruct path
- owner-only bypass
- delegatecall danger
- arbitrary external call
- unsafe upgrade path

Naming note:

Use `Symbolic Path Mapping` unless a branded internal module name is intentionally chosen.

ANCHOR rule:

- Symbolic path found does not equal bug found.
- Symbolic path found means the path deserves targeted review.
- Reproduction and measurable impact are still required.

## Operating Principle

ANCHOR stays useful by being strict about promotion.

The system can be aggressive about generating hypotheses, but conservative about claiming success.
