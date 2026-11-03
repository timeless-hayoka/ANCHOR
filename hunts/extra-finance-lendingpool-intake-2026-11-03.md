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

## Source/deployment equivalence gap

- An OP explorer URL for the target and the project's contracts documentation both refer to the same address; a fully machine-readable verified-source/bytecode comparison was **not obtained**.
- The repo's `foundry.toml` specifies solc 0.8.20 with 200 optimizer runs.
- A *Base* explorer page for the same address reports `LendingPool` compiled with solc 0.8.18 and 200 runs. This is **not verification of the Optimism build**; it is a warning to avoid assuming the repo's default toolchain reproduces deployed bytecode.
- Pending: fetch OP verified source metadata/compiler settings, deployment bytecode, linked libraries and constructor args; rebuild at exact settings, compare runtime bytecode excluding metadata/immutables as appropriate, and document the comparison before any production-equivalent claim.

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
