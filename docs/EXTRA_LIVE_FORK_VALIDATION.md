# Extra Finance Optimism: live-state read-only Foundry validation

**Date:** 2026-11-03. **Target:** OP Mainnet (chain ID 10), `0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd`. **Source:** [GitHub Actions run 41700121236](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41700121236).

## Actual onchain execution

The workflow connects to public OP Mainnet read-only RPC `https://mainnet.optimism.io`, checks `eth_chainId=10`, captures an explicit block, then executes a **pinned-block local Foundry fork**. The contract under test is the actual public LendingPool at its real deployed address and storage state. It does not deploy replacement LendingPool bytecode or mock reserve state. It can **locally simulate** an unprivileged state-changing call inside the disposable fork; no such call is sent to the public RPC or broadcast to the chain.

First passing run: [41699813858](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41699813858), **block 159066955**, **3/3 passed**.

Second passing run: [41700121236](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41700121236), **block 159067013**, **3/3 passed**. In this run the test emitted numeric and address snapshots from real contract getters; the log is archived with chain/block provenance.

- `nextReserveId() = 83` (reserve IDs 1–82 were assigned; not necessarily all currently active).
- `nextDebtPositionId() = 259` (historical debt IDs issued; not an assertion that 258 debts are currently active).
- Actual registry getter returns a contract with bytecode.
- Checked the first **8** reserve IDs (a bounded sample, not a complete 82-reserve audit).
- Getter calls within one pinned block were deterministic.
- Underlying asset and eToken addresses for all sampled reserves pointed to deployed contract code; sampled totals met the checked consistency bounds.

### Selected actual reserve data from block 159067013

All liquidity/debt values are **raw underlying token base units**; tokens have different decimals, so do not add them or interpret them as USD. Utilization and annualized borrow-rate getters return numbers scaled by 1e18.

| Reserve ID | Underlying address | Total liquidity (raw) | Total borrow (raw) | Utilization (1e18) | Borrow rate (1e18) |
|---|---|---:|---:|---:|---:|
| 1 | `0x4200000000000000000000000000000000000006` | 3798236039918026699 | 455539217560682665 | 119934415021377682 | 35980324506413304 |
| 2 | `0x7F5c764cBc14f9669B88837ca1490cCa17c31607` | 8431722544 | 23913670 | 2836154756659649 | 850846426997894 |
| 4 | `0x4200000000000000000000000000000000000042` | 59817935460025539506536 | 5664031307265049766394 | 94687843432011210 | 23671960858002802 |
| 5 | `0x8700dAec35aF8Ff88c16BdF0418774CB3D7599B4` | 3171943508267671643 | 0 | 0 | 0 |
| 6 | `0xbfD291DA8A403DAAF7e5E9DC1ec0aCEaCd4848B9` | 67275683029946896 | 29116502983053989 | 432793866546002306 | 108198466636500576 |

The full pass log also records reserve IDs 3, 7, 8, registry address and eToken addresses. Only samples are reproduced above for readability. Exact state is **block-scoped**; these are not promises about present balances or configuration.

## Live-storage security negative control (block 159067111)

[GitHub Actions run 41700661923](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41700661923) passed **4/4 Foundry tests, 0 failures** on a new pinned OP block **159067111**.

The fourth test, `test_LocalForkNonOwnerCannotInitializeReserve`, simulates an **unprivileged `initReserve` call only inside the disposable fork** using Foundry's `vm.prank`. The call reverts as expected, and `nextReserveId()` remains unchanged. The external public Optimism RPC only serves chain, code and storage reads; the simulated transaction is never broadcast or sent to the live chain.

This tests one access-control boundary against real deployed code and real starting storage. It does **not** demonstrate a bypass or exploit, and does not prove authorization safety for every administrative method, proxy or reserve state.

## Bounty research negative control: stranger borrow/repay (2026-11-03)

[GitHub Actions run 41701896193](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41701896193) ran **5/5 local fork tests, 0 failures** against OP Mainnet **block 159067350**. The new `test_LocalForkUnknownAccountCannotBorrowOrRepayExistingDebt` selected a fresh unwhitelisted test account and attempted `borrow(account, 1, 1)` and `repay(account, 1, 1)` **inside the isolated EVM fork only**. Both reverted, and the real reserve's readback liquidity, outstanding borrowing, next-reserve and next-debt counters were unchanged.

**Hypothesis status: NEGATIVE / NO BYPASS REPRODUCED.** This test does not establish a reportable issue or prove every possible vault or debt authorization edge. No public contract transaction was broadcast. The account used was not whitelisted and no program admin permission was assumed.

Current Extra Finance <https://immunefi.com/bug-bounty/extrafinance/information/> (last updated September 16, 2026) publishes four excluded known LendingPool issue families: initial-share inflation, debt/position rounding causing repayment failures, stale timestamp on first borrowing, and over-repayment increasing vault credit. These known issues must not be relabeled as novel findings. The program explicitly requires local-fork testing, permits neither direct mainnet testing nor indiscriminate attack automation, and requires a PoC for accepted reports.

**Bounty next gate:** choose a different externally reachable security invariant with a plausible accepted financial impact, demonstrate a FAIL on independent real-implementation controls in a local fork, then isolate the minimal reproduction and scope/duplicate checks before submission. The original Trinity lead remains a research signal.

## Real vault credit and admin-control negative tests (2026-11-03)

[GitHub Actions run 41718377837](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41718377837) passed **7/7 local-fork Foundry tests** against OP Mainnet block **159070543**.

These two additional tests resolve the deployed vault via the actual public `AddressRegistry.getAddress(10)` (vault factory ID) and `VaultFactory.vaults(1)`. The LendingPool's `getVault()` helper is internal and **not** an external ABI method; this matters because the first implementation incorrectly assumed it was externally available. The final verified tests inspect a real factory/vault in fork storage.

- Non-owner `setCreditsOfVault(1, 1, previousCredits + 1)`: **reverted**. The vault's credit, whitelist flag, reserve liquidity and total borrowing stayed unchanged.
- Non-owner `enableVaultToBorrow(1)`, `disableVaultToBorrow(1)`, `freezeReserve(1)` and `unFreezeReserve(1)`: **all reverted**. The vault whitelist, credit and reserve ID counter remained unchanged.
- The original 5 live-fork tests (deployment state, reserve/debt views, deterministic getters, unauthorized reserve initialization, and stranger borrow/repay rejection) also passed.

**Hypothesis outcome: NEGATIVE / NO ADMIN OR VAULT-CREDIT BYPASS REPRODUCED.** Only one deployed vault and reserve pair was sampled; the run does not certify every permissioned vault or edge condition, and there is no demonstrated economic exploit. Calls were simulated inside the local fork; the Optimism RPC was used only for state reads.

**Next distinct research directions:** complex vault callbacks and cross-reserve debt paths, real reserve configuration versus synthetic assumptions, and multiple real-vault interactions. Each needs independent scope/duplicate review, a failing invariant with concrete impact, and reproducible local-fork evidence before any Trinity finding or bounty report.

## Real cross-vault debt ownership boundary (2026-11-03)

[GitHub Actions run 41718872413](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41718872413) passed **8/8 fork tests, zero failures** at OP Mainnet block **159070638**.

The additional local-only test `test_LocalForkWhitelistedVaultCannotOperateAnotherVaultDebt` scans a bounded number of actual deployed debt IDs and factory vault IDs. It locates a debt position whose owner is a whitelisted onchain vault, and a **different**, also whitelisted onchain vault. It then simulates `borrow(otherVault, debtId, 1)` and `repay(otherVault, debtId, 1)` as that second vault inside the disposable fork.

**Both cross-vault calls reverted.** The recorded original position owner, debt principal, reserve ID, competing vault credit, total reserve liquidity, and aggregate borrowing remained unchanged. No live-chain transaction was broadcast. The test asserts that the pool is not paused to avoid counting the pause guard as an owner-check success.

**Research status: NEGATIVE / NO CROSS-VAULT DEBT OWNERSHIP BYPASS REPRODUCED.** This establishes one verified deployment snapshot and bounded pair of real whitelisted vaults, not all vaults, historical blocks, debt configurations, or a new in-scope financial loss. This evidence must not be promoted to a bounty report.

## Conclusions and boundaries

The deployed contract, actual registry and sampled live reserves are reachable; getters function consistently in a pinned-block fork. This provides real-state, source-independent confirmation beyond the synthetic reserve tests in PRs #42–#43.

**This is not a validated vulnerability**, not a full asset audit, and not a demonstration of state-mutating borrow/repay safety on production storage. The first three fork tests use only view methods; the fourth uses an **isolated local simulation** of an unauthorized admin call and asserts rollback. Public RPC reliability and archive retention may affect repeatability. The next validation should compare active reserve configuration and vault permissions against source-matched protocol invariants, using local-only fork simulations, no live broadcasts, and independent scope review before any bounty finding claim.

No Trinity lead is promoted; no report submitted.
