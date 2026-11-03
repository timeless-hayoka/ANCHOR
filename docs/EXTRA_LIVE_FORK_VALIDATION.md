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

## Conclusions and boundaries

The deployed contract, actual registry and sampled live reserves are reachable; getters function consistently in a pinned-block fork. This provides real-state, source-independent confirmation beyond the synthetic reserve tests in PRs #42–#43.

**This is not a validated vulnerability**, not a full asset audit, and not a demonstration of state-mutating borrow/repay safety on production storage. The first three fork tests use only view methods; the fourth uses an **isolated local simulation** of an unauthorized admin call and asserts rollback. Public RPC reliability and archive retention may affect repeatability. The next validation should compare active reserve configuration and vault permissions against source-matched protocol invariants, using local-only fork simulations, no live broadcasts, and independent scope review before any bounty finding claim.

No Trinity lead is promoted; no report submitted.
