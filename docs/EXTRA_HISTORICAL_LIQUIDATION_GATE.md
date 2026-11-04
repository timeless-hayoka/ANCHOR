# Extra Finance — historical liquidation eligibility gate (phase 1)

**2026-11-04.** Research-only, Optimism chain 10. All discovery reads come
from the pinned archived fork; no mainnet transaction, wallet key, storage
overwrite or synthetic oracle value is permitted.

## Read-only scanner enrichment

`tests/extra_historical_fork/AnchorExtraHistoricalPositionDiscovery.t.sol`
now reads the deployed VeloPositionManager `getVault(vaultId)` output for
each real vault in the bounded historical sample, independently of position
activation. It logs the full vault config ABI hash plus these raw fields from
the verified ABI: `liquidateWithTWAP` (word 8), `maxPriceDiff` (word 11),
and `liquidateDebtRatio` (word 12).

The scanner **always** logs `VAULT_LIQUIDATION_ELIGIBILITY_UNKNOWN` after
a valid configuration read. If the getter fails or the prefix is invalid,
it logs `VAULT_CONFIG_UNAVAILABLE`. A valid configuration alone is **not**
a proof that an observed position is unhealthy.

The reference positive control remains Optimism block 120000000,
vault 3, position 16. Its successful manager-authorized 10% close and
reserve debt/cash conservation do **not** establish liquidation eligibility.

## Remaining verified-eligibility gate

Before any liquidation replay may be represented as a real eligible transition:

1. Inspect the verified deployed manager's exact liquidation predicate and
   all transitive oracle/AMM dependencies for that deployment revision.
2. Resolve the vault's actual token addresses, reserve debt and interest,
   and onchain oracle/TWAP/spot/Chainlink values **at the same block**.
3. Apply the implementation's exact units, token decimals, precision,
   rounding, threshold and price-divergence checks; preserve the getter
   outputs and immutable block provenance.
4. Mark a position `ELIGIBLE` only if all checks are evidenced.
   Use `UNKNOWN` for missing, stale or inconsistent sources.
5. Separately simulate the permitted liquidation exclusively inside an
   ephemeral Foundry fork, reconcile position debt, protocol reserve totals,
   ERC-20 custody, fees, and liquidator/owner token deltas, and require an
   independent evidence review before promoting to a Trinity finding.

Do not infer eligibility solely from `isActive`, nonzero debt,
`liquidateDebtRatio`, or a passing local-fork close.

## Finder → Trinity handoff boundary

Finder discovery/priority does not grant authorization. A real selected
target must pass its scope confirmation and the BugBot operational
scope check. A scanner diagnostic remains a research signal, not
`reproduced_real`. The Trinity lead state machine requires independent
reproduction, a Watcher challenge and review for later promotion.

## Verification

`python -m pytest tests/test_extra_historical_liquidation_config.py -q`

The workflow's historical archive-discovery job is opt-in due public RPC
rate limits. CI controls that use an RPC must run serialized; HTTP 429
is an environmental blocker, not a vulnerability.

**Status:** phase 1 code prepared; historical fork output and complete
oracle eligibility proof not yet verified on this change.

## Oracle-aware numeric triage (phase 2)

`extra_liquidation_eligibility.py` evaluates supplied historical token
observations with integer-only, decimal-adjusted price values (`price_e18`).
It requires the same chain-10 block for every observation and fails closed for
invalid price, zero collateral, duplicates, missing provider identity, or an
unverified price source. It compares `debt_value * 10_000` to
`collateral_value * liquidation_threshold_bps` without floating point
arithmetic; equality is not treated as a breach in this *indicative* model.

**Critical limitation:** This is a screening calculation, not the deployed
vault's proven predicate. The manager delegates liquidation to its vault;
vault LP valuation, AMM TWAP/spot rules, external price comparison and exact
rounding must be reproduced from verified historical implementation first.
The module never returns `ELIGIBLE` or `reproduced_real`, even if every
caller-provided verification flag is true. A sample or test observation must
never be passed off as archived onchain data. The prior known-active
historical position is not newly declared liquidatable by this change.

## Cross-pipeline proof regression (phase 3)

`tests/test_finder_trinity_evidence_integration.py` exercises a deliberately
synthetic high-priority Finder candidate, a high-risk numeric triage result,
a Trinity `signal` record, and an evidence-dashboard fixture. Assertions
require scope to remain unknown, and both reproduction/report promotion jumps
to raise gate errors. This complements the full existing scope-confirmation,
Watcher, and published-evidence unit suites.

Run the connected regression selection:

```bash
python -m pytest -q \
  tests/test_extra_historical_liquidation_config.py \
  tests/test_extra_liquidation_eligibility.py \
  tests/test_finder_trinity_evidence_integration.py \
  tests/test_finder_pipeline.py \
  tests/test_trinity_lead_state_machine.py \
  tests/test_outcome_evidence.py
```

Passing these tests establishes **gate behavior on synthetic inputs**,
not authentic oracle provenance, protocol equivalence or a proven bounty.
A separate historical RPC-based validation is still mandatory before
liquidation simulation.
