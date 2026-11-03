# Extra Finance — LendingPool research intake (2026-11-03)

**State:** PUBLIC-SOURCE REVIEW / NOT A VULNERABILITY REPORT  
**Target:** Extra Finance LYF LendingPool, OP Mainnet  
**In-scope address (Immunefi):** `0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd`  
**Chain:** Optimism / OP Mainnet (chain ID 10)  
**Bounty:** https://immunefi.com/bug-bounty/extrafinance/information/  
**Scope:** https://immunefi.com/bug-bounty/extrafinance/scope/  
**Source:** https://github.com/ExtraFi/extra-contracts/tree/a66e925d78ee5c990eb2bafa5009cebcbeafe42d  
**Source file:** `contracts/lendingpool/LendingPool.sol`  
**Source commit:** `a66e925d78ee5c990eb2bafa5009cebcbeafe42d` (2024-12-19; GitHub commit metadata)  
**Source blob SHA:** `014b56fa96ce7968bb9cca982a903aa5420604c2`

## Public policy and impact boundary

Immunefi's page lists a live program, maximum $100,000, and no KYC required for payout; claims/terms should be rechecked before any submission. A PoC is required for every severity. The policy explicitly forbids testing deployed contracts on public mainnet/testnet, interacting with third-party oracles/contracts in tests, disrupting services, and public disclosure of unpatched findings. Any reproduction must stay in an isolated, non-broadcast local fork or owned lab.

The displayed scope includes the OP Mainnet LendingPool address above. Scope listing **is not** evidence that this GitHub revision exactly matches the deployed bytecode. Do not label any source-only hypothesis `REPRODUCED_REAL`.

## Source inspection — observed entry points

Pinned file `LendingPool.sol` includes:
- `deposit`, `depositAndStake`, `_deposit`: reserve state update, receipt eToken mint, initial locked shares.
- `redeem`, `unStakeAndWithdraw`, `_redeem`: eToken transfer/burn and underlying payout, available-liquidity check.
- `newDebtPosition`: creates debt ownership tied to caller and reserve (inspect this path with borrow authorization).
- `borrow`: vault whitelist AND debt-position owner required; consumes per-vault credit.
- `repay`: vault whitelist AND debt-position owner required; clamps to recorded debt and pool borrows.
- Administrative reserve, vault and credit controls: `onlyOwner`.

These are code observations, **not** claims of exploitability. Source inspection covered these functions; dependent libraries and vault integrations need full call-path review.

## Published known issues — duplicates to exclude

The official Immunefi information page lists these as known (as of the 2026-09-16 program update):
1. First-depositor share-inflation pattern for an empty reserve, mitigated by locked initial shares.
2. Debt repayment failure due to divergence of aggregate and per-position rounding.
3. `lastUpdateTimestamp` not advancing while total borrows are zero, overstating first borrow interest.
4. `repay()` credit accounting for overpayment, with access restricted to whitelisted vaults.

**Do not submit these mechanisms as new findings.** Their variations need rigorous distinction and reproduction to overcome duplicate risk. Published PeckShield and BlockSec audit reports are referenced by the bounty; unfixed issues contained in them are ineligible. Those PDF findings have **not** been fully triaged in this intake.

## Reproducible read-only source comparison

The branch now includes `scripts/check_extra_lendingpool_source.py`, which asks Sourcify v2 for the **Optimism chain 10** target and compares the pinned `LendingPool.sol` source text. This is a read-only public metadata request, not interaction with the onchain contract.

```bash
# From an ExtraFi/extra-contracts checkout at a66e925d78ee5c990eb2bafa5009cebcbeafe42d:
python /path/to/ANCHOR/scripts/check_extra_lendingpool_source.py \
  --source contracts/lendingpool/LendingPool.sol
# Or use a captured Sourcify API v2 JSON response without any network:
python /path/to/ANCHOR/scripts/check_extra_lendingpool_source.py \
  --source contracts/lendingpool/LendingPool.sol \
  --snapshot sourcify-lendingpool-op.json
```

`PINNED_SOURCE_MATCH` means one source file agrees with a chain-specific Sourcify exact-runtime-verified source entry; it **does not** establish that the complete GitHub repository or its Foundry build reproduces the deployed bytecode. Missing metadata, non-exact runtime verification, failed requests, wrong network/address, or different source content yield `NOT_VERIFIED` (exit 2). The independent source comparison has **not yet produced a verified result for this target**; the current environment could not retrieve the exact onchain proof. The unit tests use fabricated snapshots only.

## 2026-11-03 automated public-source check — NOT VERIFIED

GitHub Actions run [41642082384](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41642082384) checked out the pinned ExtraFi source commit, passed the offline verifier tests, and requested Sourcify chain-10 deployment metadata. The public-source comparison emitted `status: NOT_VERIFIED` with reason `Sourcify exact runtime match not established`, and uploaded the evidence artifact `extra-lendingpool-source-evidence`. The collection job itself succeeded because it records evidence independently of result status; its green status is **not** contract verification. Further automated runs now also preserve `reported_runtime_match` to distinguish a nonexact source verification from absent verification.

No bytecode equivalence, production-level issue, or novel bug is claimed. Next: compare Etherscan's Optimism verified build metadata and all included source units, or determine whether Sourcify reports a non-exact runtime match. Use an isolated fork only after establishing the appropriate deployed-code mirror.

## Sourcify verified-source delta — independently observed 2026-11-03

A subsequent isolated GitHub Actions read-only verification produced a non-exact Sourcify runtime verification (`runtimeMatch: match`) but **the pinned GitHub `LendingPool.sol` did not equal Sourcify's verified `LendingPool.sol`**. Evidence:
- GitHub pinned file: SHA-256 `f6150adb79b54d439b931633ab2aa606621b03ba157b26b62476ca5f8ac51f14`, 833 lines.
- Sourcify verified source: SHA-256 `9e1a6cf5930e2477aab0022536be39ab4bb7e1fbb6953b31cf90429f6205bf6f`, 820 lines.
- Bounded line-oriented comparison found **12 distinct changed regions**. An example early region is source lines 185 versus verified lines 182-189; several additional regions overlap public LendingPool entry-point and accounting sections. This is *not* proof that the changed lines alter behavior or introduce exploitable security defects.
- Evidence workflow: [GitHub Actions 41642968123](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41642968123); results are captured in uploaded `extra-lendingpool-source-evidence` artifact.
- Classification: `NOT_VERIFIED` **for the pinned repo file**; Sourcify itself reports a non-exact runtime verification for the deployed source.

**Consequence:** Do not use the pinned GitHub checkout as an unquestioned production-equivalent source mirror. Obtain the verified source tree, reconcile version and compiler settings, and reproduce on an isolated fork before drawing conclusions or submitting a report. The timestamp and credit-known-issue discrepancies might reflect source drift, but no causal chain or novelty has been established.

## 2026-11-03 Solidity token-level source comparison

[GitHub Actions source evidence run 41646844548](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41646844548) checked the pinned ExtraFi repository against the Sourcify non-exact-runtime verification. After excluding Solidity whitespace and comments (without discarding literal strings), the two source files are still **TOKEN_DIFFERENT**:
- Pinned GitHub `LendingPool.sol`: **3,451** Solidity-like tokens.
- Sourcify verified-source `LendingPool.sol`: **3,329** tokens.
- **13 token-level changed regions**, separately from the 12 line-oriented changed regions.
- The `security_conclusion` output is explicitly `NONE`.
- The live-source check's top-level status remains `NOT_VERIFIED` for the pinned repository.

The classifier is intentionally conservative: different tokens show code-level source drift, **not** necessarily different runtime behavior or an exploitable bug. The Sourcify verification is non-exact, so full bytecode equivalence remains unproven. Next: inspect exact differences and relevant published audit reports, pin the actually deployed build, then test approved invariants in isolation.

## Source/deployment equivalence gap

- An OP explorer URL for the target and the project's contracts documentation both refer to the same address; a fully machine-readable verified-source/bytecode comparison was **not obtained**.
- The repo's `foundry.toml` specifies solc 0.8.20 with 200 optimizer runs.
- A *Base* explorer page for the same address reports `LendingPool` compiled with solc 0.8.18 and 200 runs. This is **not verification of the Optimism build**; it is a warning to avoid assuming the repo's default toolchain reproduces deployed bytecode.
- Pending: fetch OP verified source metadata/compiler settings, deployment bytecode, linked libraries and constructor args; rebuild at exact settings, compare runtime bytecode excluding metadata/immutables as appropriate, and document the comparison before any production-equivalent claim.

## Library follow-up and apparent timestamp discrepancy

Additional pinned sources inspected:
- `contracts/libraries/logic/ReserveLogic.sol` (blob `720220963b431eb44af666dde9575bf9fcd9fe3b`): exchange-rate and borrow-index math; `_updateIndexes` computes debt interest conditionally, but assigns `reserve.lastUpdateTimestamp = uint128(block.timestamp)` **outside** the `totalBorrows > 0` condition.
- `contracts/lendingpool/ExtraInterestBearingToken.sol` (blob `c4a24d65dd39f7939cd9c4ae67e5694226eb9d42`): only-LendingPool mint, burn, and underlying transfers.
- `contracts/lendingpool/StakingRewards.sol` (blob `0ebdf9b9956f9ee7ff1fea019b95eb2e7e433765`): `withdrawByLendingPool` checks the LendingPool caller and debits the named user's stake.
- `contracts/Payments.sol` (blob `c3cd0d3022a2068ca0450da033ead06e69274cf3`): native-WETH wrapping, WETH unwrapping, and refund paths.
- `contracts/VaultFactory.sol` (blob `d92545d9c50c0839dcbe9756c81d52c1fa83b36d`): vault deployment entry points (full vault call graph still pending).

**Consistency question:** The Immunefi published known issue says the zero-borrow timestamp fails to advance. The pinned repository's `ReserveLogic._updateIndexes` visibly writes the timestamp regardless of borrow count *when called*. This may mean the known issue describes an older revision, that a relevant path never calls `updateState`, or that the deployed Optimism bytecode differs. It is not itself proof of source divergence, remediation, or a novel defect. Verify the deployed implementation and execution paths before interpreting the known issue.

A separate caution: the `Payments.unwrapWETH9` helper uses the contract's full WETH balance rather than only its minimum-amount parameter. Assess accounting and invocation assumptions in an isolated harness before drawing any security conclusion; no impact has been shown.

## Candidate invariants for isolated validation (not findings)

- Redemption cannot release more underlying than the redeemer's properly accounted eToken shares, subject to the documented rounding model.
- Across a complete borrow/repay lifecycle, reserve-level debt and all affected position debt stay consistent within an explicitly bounded rounding tolerance. Known repayment-rounding behavior must be treated as a baseline limitation, not a newly discovered bug.
- Untrusted callers cannot borrow or repay for another vault's debt position; whitelisted vault callers must still satisfy per-position ownership checks.
- Staking and unstaking must not double-count eTokens or enable withdrawal of another user's stake.
- Paused/frozen/inactive flags must enforce the *intended* transition semantics across deposit/redeem/borrow/repay. Check specification before asserting invariants.

## Next reproducible steps

1. Acquire and inspect the OP explorer verified source and deployment metadata; record bytecode/build comparison and immutable settings. **Blocked: production-equivalent reproduction until this is established.**
2. Review the PeckShield and BlockSec audits and maintain a mechanism-level duplicate register.
3. Inspect the pinned `ReserveLogic.sol`, eToken, `Payments.sol`, staking, `VaultFactory` and vault debt call paths; map trust boundaries and all state mutations.
4. Build isolated Foundry tests against a verified-code mirror or a local fork. Do not broadcast transactions or call live contracts.
5. Retain separate states: `SIGNAL` -> `HYPOTHESIS` -> `LOCAL_REPRODUCTION` -> `EVIDENCE_REVIEW`; no finding promotion without proof of novelty, in-scope impact, and permission.

**Evidence status:** public policy and source read, known-issue list extracted, code target pinned. No PoC executed, no vulnerability verified, no bounty submitted.
