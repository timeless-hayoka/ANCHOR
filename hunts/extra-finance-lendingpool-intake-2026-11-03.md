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

## Source diff hotspot triage (2026-11-03, live Sourcify evidence)

The source-difference classifier ran against the *verified* Optimism source with `runtimeMatch: match` and produced **13 Solidity token change hunks** (3,451 vs 3,329 tokens). The line-oriented classifier attributes its 12 changed regions to their nearest named functions. These are candidate code-review locations **not** identified vulnerabilities:

| Pinned source lines | Nearest function | Triage rationale |
| --- | --- | --- |
| 1, 20, 27–29 | Contract header/imports | Check interface, compiler, inheritance and constants. |
| 185 | `redeem` | Compare eToken receipt handling and beneficiary accounting. |
| 224 | `unStakeAndWithdraw` | Compare withdrawal orchestration with staking accounting. |
| 277–287 | `_deposit` | Compare actual incoming funds and eToken mint arithmetic. |
| 452–462 and 468 | `repay` | Compare debt adjustment, clamping and credit paths; known repayment issues overlap and must be excluded. |
| 535–538 and 558–559 | `setBorrowingRateConfig` | Compare privileged configuration validation. |
| 789–792 | `setReserveFeeRate` | Compare fee-setting safeguards. |

Evidence: [GitHub Actions source-evidence run 41647190600](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41647190600). Nearest-function association is a *textual heuristic* rather than an AST or a proof of changed behavior.

**Next gate:** recover and review each changed source body from the independently verified compiler input, compare with released audit reports and known-issue exclusions, and only then build non-broadcast Foundry invariants. Do not promote any of these differences to a bounty submission without a distinct, reproduced in-scope impact.

## Historical audit duplicate register (PeckShield 2023-098)

Primary report: [PeckShield ExtraFi v1.0 (May 5, 2023)](https://github.com/peckshield/publications/blob/master/audit_reports/PeckShield-Audit-Report-ExtraFi-v1.0.pdf). The report identifies **a different repository and revision**: `ExtraFi/contracts` reviewed commit `c70f83d` and post-fix commit `ebed8b1`. This must not be conflated with the current pinned `ExtraFi/extra-contracts` commit `a66e925d...` or with deployed Optimism bytecode.

Published findings in the 2023 audit, to exclude from novelty claims:
- **PVE-001 (High; resolved):** Possible Position Value Manipulation, affecting position leverage valuation and reserve-derived amounts.
- **PVE-002 (Low; resolved):** Accommodation of Non-ERC20-Compliant Tokens.
- **PVE-003 (Low; resolved):** Incorrect `VeToken.balanceOfAt()` Calculation.
- **PVE-004 (Low; resolved):** `StakingRewards.setReward()` logic improvement.
- **PVE-005 (Medium; mitigated):** Trust Issue of Admin Keys.
- **PVE-006 (Informational; resolved):** Redundant State/Code Removal.

The older report states all issues except admin-key trust were marked resolved, with admin risk mitigated. Extra Finance's current bounty rules exclude unfixed issues mentioned in its listed audits. **Historical status is not proof that any current deployment is fixed**; verify the actual runtime and separate the dated audit scope from the verified source delta. The BlockSec and Sherlock findings are not yet fully triaged against these source hunks.

## Token identifier delta review — prevalidation signals, NOT findings

GitHub Actions [run 41647727141](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41647727141) recorded **13 token-difference regions** without dumping verified source code. Changed-identifier summaries point to these areas:

| Source drift indicator | Research classification |
| --- | --- |
| `MINIMUM_ETOKEN_AMOUNT`, `DEAD_ADDRESS`, initial eToken `mint` and `totalSupply` appear in the pinned GitHub version but not the same locations in verified source | **KNOWN-ISSUE OVERLAP**: initial share-inflation / locked minimum shares is already disclosed by the program; assess versioning only, not a novel claim. |
| `repay` branch identifiers include `debtPosition.borrowed`, `reserve.totalBorrows`, `amount` and subtraction logic on both sides in different positions | **KNOWN-ISSUE OVERLAP**: repayment rounding and credit handling disclosed in program; compare control flow, but no bounty claim without distinct mechanism. |
| `payable` and `avoidUsingNativeEther` vary around redeem/unstake functions | **SPECIFICATION REVIEW**: determine intended WETH/native-ETH semantics and whether a source version change alters a supported path. No impact shown. |
| `setBorrowingRateConfig` and fee configuration call-path terms differ | **ADMIN/CONFIG REVIEW**: owner authorization and parameter checks must be assessed with the deployed verified source; no unauthorized state change demonstrated. |

The classifier removes whitespace and comments, but preserves Solidity-like tokens and literals; it is not an AST verifier, compiler equivalence proof, or exploit test. The live source's Sourcify runtime verification remains **non-exact**. None of these differences should be promoted beyond a research hypothesis until confirmed against an appropriate deployed-code mirror and audit history.

## Verified source: exact changed statements (2026-11-03)

The read-only source-review workflow [run 41649997589](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41649997589) retrieved Sourcify's verified-source listing for OP Mainnet, `runtimeMatch: match` (non-exact). The pinned GitHub and Sourcify sources differ in **12 line hunks** and **13 lexical token hunks**. Exact review of the 12 line hunks provides these conservative conclusions:

| Path | Difference | Interpretation |
| --- | --- | --- |
| File header | SPDX MIT in pinned GitHub vs GPL-3.0 in Sourcify | License/source provenance difference; not security impact. |
| Import | `../address-registry/AddressRegistry.sol` vs `../AddressRegistry.sol` | Different source layout; build settings and dependency resolution matter. |
| Initial supply | Pinned GitHub has `MINIMUM_ETOKEN_AMOUNT = 1000`, dead address, and first-share locking; Sourcify source lacks that block | Matches the publicly disclosed first depositor inflation issue family. Must be treated as a known issue. |
| `redeem`, `unStakeAndWithdraw` | Sourcify adds `payable` plus `avoidUsingNativeEther` | The modifier requires zero `msg.value`, so payable alone is **not** evidence of an ETH-acceptance vulnerability. |
| `repay` | Pinned GitHub caps repayment against both position debt and reserve total borrows; Sourcify caps against position debt only, with subtraction after credit handling | Repayment accounting is a published known-issue area. Analyze aggregate versus position debt, but do not submit duplicate mechanism. |
| `setBorrowingRateConfig` | Pinned GitHub additionally validates utilization thresholds and updates reserve state/rates | Owner-authorized configuration and user impact unproven; specification and deployed runtime needed. |
| `setReserveFeeRate` | Pinned GitHub updates reserve state and rates around fee change; Sourcify assigns fee directly | Owner-authorized fee setting; potential accounting timing differences remain a hypothesis, not an impact claim. |

**Source provenance gate:** The Sourcify runtime verification is `match`, not `exact_match`; source files are not identical to the pinned GitHub revision. Do not call the pinned revision a deployed equivalent. The source review script is a textual comparison; there is no Foundry reproduction or novel impact demonstrated from these differences.

The branch also adds `.github/workflows/extra-finance-lab-baseline.yml` to run the upstream repository's existing LendingPool, eToken and staking Foundry tests in isolation, without fork RPC credentials or broadcast. Existing upstream tests are useful for environment and baseline checks **only**, not a proof against the deployed Sourcify version.

## Isolated Foundry upstream baseline — verified 2026-11-03

[GitHub Actions run 41650590053](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41650590053) successfully compiled the *pinned GitHub revision* `a66e925d78ee5c990eb2bafa5009cebcbeafe42d` with its Forge-configured Solidity compiler `0.8.20`. In isolated CI with no fork RPC or broadcast, the compatible positive test suites returned:
- `ExtraInterestBearingToken.t.sol`: **2 passed**.
- `LendingPool.t.sol`: **3 passed**.
- `StakingRewards.t.sol`: **4 passed**.
- **Total 9 passed / 0 failed**.

**Limitation:** Five historical tests named `testFail*` were *excluded*, not passed. Current Forge rejects that obsolete convention; the CI job records them separately in the `legacy-testfail-tests.txt` artifact. Those negative controls still require explicit modernization. Neither the nine positive tests nor compiler success establish that the source matches the Sourcify-verified Optimism runtime.

**Immediate next tasks:** build modern negative controls using `vm.expectRevert` in an isolated forkless harness, confirm the relevant authorization and insufficient-share failures, and then repeat against correctly matched deployed-source input. No production interaction.

## Full pinned Foundry baseline with modernized negative controls

Run [41651290826](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41651290826) compiled pinned commit `a66e925d78ee5c990eb2bafa5009cebcbeafe42d` and executed all existing LendingPool, eToken and staking tests inside a non-broadcast CI environment:

- **14 passed, 0 failed, 0 skipped**, across three test suites.
- Exactly five `testFail*` functions were converted to modern `test_RevertWhen*` form in an **ephemeral checkout only**, using `scripts/extra_legacy_test_adapter.py`. The adapter does not change the protocol repository on GitHub.
- The first attempted modernization honestly produced 11 passed / 3 failed due to two stale `Ownable` revert-message expectations and one flawed pre-assertion burn test setup. All were corrected in the scoped ephemeral adapter before the passing run.
- CI preserves pinned-source provenance, Forge version and test output.
- The current branch also includes adapter self-tests. Revalidate the final commit's CI independently before merging.

**Important:** This is a passing test baseline for the *pinned repository*, not the verified Optimism implementation. Because Sourcify's verified `LendingPool.sol` differs in executable tokens, this result does **not** establish that the deployed version passes identical checks. Existing test cases also do not cover the full economic invariant space. Novel vulnerability evidence remains **NONE**.

## Actual Sourcify deployment metadata (2026-11-03)

The new read-only `scripts/anchor_deployment_provenance.py` collected the real Sourcify v2 `fields=all` verification metadata in [Extra Finance evidence run 41657612177](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41657612177):

- Deployment: chain `10`, target `0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd`.
- `compilation.fullyQualifiedName`: `contracts/lendingpool/LendingPool.sol:LendingPool`.
- **Compiler: `0.8.18+commit.87f61d96`**; optimization enabled, **200 runs**.
- Sourcify lists **33 verified source files**; `LendingPool.sol` SHA-256 is `9e1a6cf5930e2477aab0022536be39ab4bb7e1fbb6953b31cf90429f6205bf6f`.
- `runtimeMatch: match` (not `exact_match`); the onchain and recompiled runtime bytecode in this provider's response were **not byte-identical**. This may be explained by permitted transformations/metadata and must **not** be called either an exploitable mismatch or independent bytecode parity.
- Provider proxy-resolution reported `isProxy: false` for this address. This is a read-only provider classification, not a guarantee that all upstream integrations are non-upgradeable.
- Independent chain-RPC bytecode attestation: **NOT PERFORMED**. Full source/build equivalence: **NOT PROVEN**.
- The upstream repository's `foundry.toml` uses **0.8.20** and its Hardhat config uses **0.8.18**; only a compiler/build matched to the verified deployment can underpin production-equivalent tests.

The associated ANCHOR handoff generated a deterministic Trinity `signal` with `BLOCKED_RESEARCH_SIGNAL`. No scope authorization, PoC, new vulnerability, or bounty claim has been produced.

**Next research gate:** capture Sourcify's standard compiler input and transformation details, run an exact 0.8.18 isolated source build, then compare produced and independently obtained runtime bytecode with appropriate transformation handling before testing protocol invariants.

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
