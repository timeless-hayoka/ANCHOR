# Extra Finance — deployed vault liquidation provenance inventory

**2026-11-04.** Optimism chain 10, archived block **120000000**,
real VaultFactory vault **3**, position **16**. All state observations must be
read from the same block in a disposable local Foundry fork. There is **no**
liquidation-eligible finding or liquidation replay in this phase.

## Verified call path and known source boundary

The pinned ExtraFi/extra-contracts commit
`a66e925d78ee5c990eb2bafa5009cebcbeafe42d` shows:

1. `VeloPositionManager.liquidateVaultPositionPartially` uses
   `liquidatorInWhitelist`, resolves `VaultFactory.vaults(vaultId)`,
   delegates to `IVeloVault(vault).repayAndLiquidatePositionPartially(...)`,
   and handles token transfers/refunds and the liquidation event.
2. `VaultTypes.VeloVaultState` includes `pair`, `token0`,
   `token1`, `stable`, `liquidateWithTWAP`, `maxPriceDiff`,
   `liquidateDebtRatio` and LP/share/debt fields.
3. The **vault's implementation** performs the deeper liquidation operation;
   the manager ABI and the protocol's public user documentation are not
   sufficient to prove its exact LP valuation, rounding, oracle/Chainlink
   selection, or price-divergence guard. Upstream contracts are only a
   source reference until deployed bytecode/version correspondence is proven.

Official Extra Finance price-feed documentation describes AMM spot pricing,
30-minute TWAP liquidation mode, and Chainlink discrepancy protection. These
are documented *intended behavior*, not substitute evidence for the exact
historical onchain implementation.

Sources:
- https://github.com/ExtraFi/extra-contracts/blob/a66e925d78ee5c990eb2bafa5009cebcbeafe42d/contracts/VeloPositionManager.sol
- https://github.com/ExtraFi/extra-contracts/blob/a66e925d78ee5c990eb2bafa5009cebcbeafe42d/contracts/libraries/types/VaultTypes.sol
- https://docs.extrafi.io/extra_finance/leverage-farming/price-feed

## New actual-storage dependency probe

`tests/extra_historical_fork/AnchorExtraHistoricalOracleProvenance.t.sol`
will resolve the onchain manager and factory through LendingPool/registry,
then read **the real vault #3** and its position #16 in a pinned archive fork:

- Vault, manager and AMM pair runtime bytecode hashes;
- Vault ABI hash and underlying token, gauge, pair addresses;
- Actual `liquidateWithTWAP`, `maxPriceDiff` and liquidation
  debt-ratio parameters at that historical block;
- Actual pair reserves, last-reserve timestamp, LP supply and the
  vault's direct LP holdings, where corresponding getters exist;
- Token decimals and the position's raw LP liquidity/debt fields;
- Manager permissionless-liquidation configuration, if exposed.

LP `balanceOf(vault)` is **not** necessarily the whole position's
collateral; the LP may be staked at a gauge or accounted via vault shares.
Reserves and supply alone do not prove the vault's valuation or a TWAP.
Optional getter failure is logged as unavailable, never converted to zero.

This probe emits `ORACLE_PREDICATE_UNVERIFIED=1` and
`LIQUIDATION_ELIGIBILITY_UNKNOWN=1` regardless of observed debt ratio.
The `oracle_verified` boolean in the existing numeric triage code is
caller-supplied, **not a cryptographic or independently authenticated oracle
attestation**. Therefore numeric triage must remain unconfirmed.

## Execution and acceptance

Pull-request CI should compile the Solidity probe **without RPC**.
The archival RPC job is separately manual via
`.github/workflows/extra-finance-historical-oracle-provenance.yml`:
single historical block, serialized, no production writes, no broadcast,
no storage changes. HTTP 429 means environment blocked, not a contract bug.
Preserve block, chain, codehashes, raw ABI and exact snapshot logs.

The next stage requires resolving the vault's **deployed implementation
identity** (including proxy/delegatecall/library dependencies) and
source-to-bytecode provenance. Reconstruct and compare real:
1. LP position share conversion / accrued farm fees / gauge holdings;
2. AMM spot and genuine historical TWAP paths, including observation
   windows and stable-vs-volatile pair math;
3. Applicable Chainlink feed identities, feed decimals, round IDs,
   timestamps and price-divergence conditions;
4. Debt accrual/index, valuation units and the exact liquidation predicate;
5. Liquidator whitelist/access and liquidation-size/fee constraints.

Only then promote an independently eligible archived position to a
**fork-only** liquidation replay with measured before/after debt, token
balances, pool reserve cash, LP supply, owner and liquidator token flows.
Replay must fail closed on missing price/feed or source equivalence, and
must not use storage/oracle overrides to force eligibility. Finder →
Trinity → evidence gates remain mandatory for any claimed finding.

## Regression command

```bash
python -m pytest -q tests/test_extra_historical_oracle_provenance.py \
  tests/test_extra_liquidation_eligibility.py \
  tests/test_finder_trinity_evidence_integration.py
```

**Status:** Historical provenance probe code prepared; actual archive probe
has not yet produced a successful readout in this PR. Exact deployed vault
predicate and eligibility remain **UNKNOWN**.
