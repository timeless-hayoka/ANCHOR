# Extra Finance: source-matched, forkless stateful LendingPool lab

Date: **2026-11-03**. Target: Extra Finance Optimism LendingPool `0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd` (chain 10).

## Source evidence

`scripts/extra_verified_stateful_sources.py` obtains Sourcify's `fields=all` metadata and materializes the embedded **33-file Solidity Standard JSON source tree** into an isolated temporary directory. The extractor enforces:

- Matching chain ID and deployed contract address.
- Solidity **0.8.18** as recorded by Sourcify, rather than the old ExtraFi GitHub `foundry.toml` default of 0.8.20.
- Verified `contracts/lendingpool/LendingPool.sol` SHA-256 `9e1a6cf5930e2477aab0022536be39ab4bb7e1fbb6953b31cf90429f6205bf6f`.
- Safe relative Solidity paths and embedded source contents only; no arbitrary remote import URLs.
- New destination only. The helper never overwrites an existing source directory.

The independent bytecode work in PRs #38–#39 established that the separately compiled verified-source runtime matches Sourcify's recompiled runtime, the RPC `eth_getCode` matches Sourcify's onchain runtime, and all 108 byte changes occur inside 12 declared metadata/immutable transformation regions. This lab **does not** reproduce the live storage, historical reserve state, owner privileges, chain state, or immutable values beyond what its own test constructors supply. Its source is verified, but its state/configuration is *synthetic*.

## Isolated Foundry experiment

`.github/workflows/extra-finance-verified-stateful.yml` downloads no private RPC endpoint, provides **no broadcast credentials**, compiles verified contracts with Foundry using Solidity 0.8.18 and optimizer runs 200, and uses separate lab-only ERC-20 and vault-factory/registry mocks.

`tests/extra_verified_stateful/AnchorVerifiedStateful.t.sol` tests:

| Control | What it asserts |
| --- | --- |
| Two-user deposits | Reserve underlying balances and individual eToken receipts are conserved |
| Unauthorized borrowing/reserve administration | Non-owner initialization and non-whitelisted borrow revert with no asset transfer |
| Borrow and repay | Debt, available reserve liquidity and vault credits move consistently within one block |
| Credit and debt authorization | Whitelist, debt ownership and credit bounds reject invalid borrowing |
| Interest accrual | Positive borrowing rate and utilization produce strictly increasing debt/index over seven simulated days |
| Pause/resume | Paused debt creation and deposits revert without changing reserves; unpause restores deposits |
| Fuzz deposit | 256 random first-deposit amounts conserve underlying and eToken ownership |
| Fuzz borrow/repay | 256 random borrowed amounts conserve vault credits, reserve liquidity and same-block debt after full repayment |

Evidence: [Actions source-matched stateful run 41689723972](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41689723972) reported **12 tests passed, 0 failed**, with 256 executions per fuzz property (512 randomized cases total). Python source-provenance regression tests: **3 passed**.

Additional CI-tested controls (2026-11-03):
- **Two-stage partial repayment:** Borrow 100,000, repay 40,000 and then 60,000 in the same block. Assert exact remaining debt, restored credits, and liquidity conservation at each step.
- **Failed-repayment rollback:** Borrow 90,000, attempt to repay 30,000 without token approval, assert that debt, credit, and reserve balances remain unchanged on revert.
- **Accrued-interest partial settlement:** Borrow 100,000, advance the isolated clock seven days, confirm debt/index growth, then repay 50,000; debt must decrease but remain positive.
- **Full accrued-interest settlement:** Fund the isolated vault for its additional accrued interest, repay the full seven-day debt, assert outstanding debt is zero, and verify transfer of accrued interest to the reserve.

The full settlement test is **not** evidence that interest always settles correctly under other time windows, extreme utilization, multiple positions, fee-on-transfer tokens or rounding edge cases. It validates the stated scenario only.

## Limits and next gates

These tests establish source-matched **lab behavior** only, not reportable findings.  The isolated contract was freshly deployed with synthetic registry, mock ERC-20 and vault factory, not loaded with the onchain contract's historical storage configuration. The seven-day interest settlement succeeds in the tested scenario and does not rule out already disclosed repayment rounding or credit problems. The borrow/repay control checks same-block repayment and does **not** assert safety under the already disclosed repayment/rounding issue families. The depositor test does **not** claim the first-share-lock mitigation present in the older GitHub revision exists in deployed source. The lab does not yet reconstruct mainnet reserve configuration, vault implementation callbacks, oracle state, liquidations, multi-reserve debt, or all security invariants.

Next: negative-control mutations of accounting/authorization assertions; additional partial repayment and interest-sensitive settlement tests; reconstruct distinct scope-approved vault/market configurations; review known findings and active bounty eligibility before any PoC or disclosure. Trinity remains `signal` with no finding.
