# Extra Finance — authentic archived LP/oracle observations (2026-11-04)

**Scope and evidence**: Optimism chain ID 10, block **120000000**,
Extra Finance vault **3**, position **16**. These are **read-only historical
fork** results from the original, actual deployed contracts; no transaction
broadcast, privileged storage write, synthetic collateral, oracle override
or reproduction of liquidation has occurred.

- [Historical identity/LP run 41828379609](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41828379609): **1/1 passed**.
- [Historical gauge/share/oracle run 41828797230](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41828797230): **1/1 passed**.
- Exact raw observations in
  `evidence/extra_finance_op_120000000_vault3_position16_oracle_snapshot.json`.

## Confirmed deployed identities

- Vault address: `0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9`.
  Runtime codehash: `0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480`.
- Velodrome OP / USDC.e pair: `0x47029bc8f5CBe3b464004E87eF9c9419a48018cd`.
- Gauge: `0x0299d40E99F2a5a1390261f5A71d13C3932E214C`.
- Chainlink adapter from actual AddressRegistry key **107**:
  `0xBEdfdA828475005Dc8E4a09Aaa34BD0b8CA807e4`.
- Deployed manager: `0xf9cFB8a62f50e10AdDE5Aa888B44cF01C5957055`.
  Historic getter `permissionLessLiquidationEnabled()` returned **false**.
  This is separate from liquidation *health*; historical liquidators
  must satisfy the actual authorization gate.

## Exact historical state

| Observation | Raw result |
|---|---:|
| `liquidateWithTWAP` | `true` |
| `maxPriceDiff` | `2000` |
| `liquidateDebtRatio` | `8334` |
| AMM token0 OP reserve (18 decimals) | `15578519655038332201614` |
| AMM token1 USDC.e reserve (6 decimals) | `39077850250` |
| Total AMM LP supply | `24649355991593486` |
| Vault direct LP balance | `0` |
| Vault `totalLp` | `85182429644961` |
| Gauge's LP balance attributed to vault | `85182429644961` |
| Vault `totalLpShares` | `81836825646430` |
| Position #16 LP quantity | `40055866659254` |
| Position #16 token1 debt | `40894860` |
| Registered Chainlink adapter `getPrice(OP, USDC.e)` return flag | `true` |
| Chainlink adapter quote, raw | `398212029812978622000000000000` |

**Independent vault custody check:** `gauge.balanceOf(vault) == vault.totalLp`
at the pinned block, despite `pair.balanceOf(vault) == 0`. No LP-loss
claim follows. Any collateral equation must account for actual gauge
and vault LP-share bookkeeping.

As a *diagnostic only*, ordinary pro-rata AMM reserves for the recorded
LP quantity yield **25.315513568127227154 OP** and **63.502558 USDC.e**,
using integer floor division. This is NOT proof of the vault's exact
redemption proceeds, full farm position value, cumulative rewards, or its
TWAP liquidation valuation. It is not a spot-price-independent dollar
valuation.

## Critical source-equivalence blocker

The deployed **vault** address is shown as **unverified** on the current
[OP Mainnet explorer](https://optimistic.etherscan.io/address/0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9#code).
The Sourcify API v2 contract lookup currently returned **404 / no match**.
The published `ExtraFi/extra-contracts` revision includes the
`VeloPositionManager` liquidation entry point, `VaultTypes` and
`IVeloVault` interfaces, but a matching **complete deployed vault
implementation** has not been obtained and fingerprinted. Do not infer
the source's internal liquidation math or call `getPrice()` a verified
USD price based solely on its raw bytes.

The pinned upstream code shows that the manager delegates the liquidation
to `IVeloVault.repayAndLiquidatePositionPartially` after the
liquidator-whitelist gate. Public protocol documentation describes a
30-minute TWAP and Chainlink price comparison; this is **not** an exact
source-equivalent onchain implementation of those requirements.
`maxPriceDiff=2000` and the adapter's raw quote have deliberately
**not** been assigned an unverified unit or quote direction.

Historical `getPosition(uint256)` did not produce the expected complete
15-word ABI payload in the test; this result is **UNAVAILABLE**, not proof
that positions lack LP-share storage. We have the separate live manager
19-word position ABI hash and actual LP/debt getter values.

## Next strict gates

1. Obtain and verify the exact historical vault runtime/implementation
   source (or demonstrate authoritative source equivalence via bytecode
   matching). Identify delegatecall/facet/library dependencies and version.
2. Reconstruct actual position-to-vault LP-share, accrued interest, and
   reward/fee conversions from that source.
3. Verify historical AMM stable/volatile variant, spot quote, its actual
   30-minute TWAP observation window, and the precise Chainlink adapter
   quote direction/scale, freshness and comparison guard.
4. Verify and apply the **exact** deployed liquidation predicate and the
   authorized liquidator restriction. Candidate result remains **UNKNOWN**
   if any value, source match, or required oracle constraint is unavailable.
5. Search for a position proven unhealthy with real historical storage.
   Only after it passes all gates, replay liquidation on an isolated fork;
   independently reconcile accrued debt, reserve ERC-20 custody, LP/share
   totals, vault and gauge LP, owner/liquidator balances and all fees.
6. Continue Finder scope checks, Trinity proof gates, independent Watcher
   review and private disclosure rules. Do not promote an expected
   transition to a bounty issue.

**Verdict**: authenticated historical *raw storage*, gauge-custody
reconciliation and an actual oracle-adapter response are **VERIFIED**.
Exact vault liquidation eligibility remains **UNKNOWN**. No valid
liquidation was attempted; no vulnerability or bounty has been found.

## Reproduction

```bash
python -m pytest -q tests/test_extra_historical_oracle_snapshot.py
```

The tests are deterministic checks on saved observations and do not
pretend to query current or archived RPC. The historical fork evidence
is separately linked above; the original GitHub Actions artifacts have
limited retention. This report and its snapshot are the durable
repository record.
