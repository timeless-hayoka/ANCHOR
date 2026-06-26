# HUNT HYPOTHESIS TEMPLATE

Use this template for every serious lead before spending too much time on it.

---

## Target

- Program:
- Contract:
- Chain:
- Commit / deployment:
- In-scope impact being tested:

## Claim

One sentence:

`I think [state transition] lets [actor] cause [harm] because [mechanism].`

## Scope Check

- Contract in scope:
- Impact in scope:
- Known exclusion conflict:
- Notes:

## Code Path

- Entry function:
- Internal path:
- External calls:
- Storage touched:
- Assets or shares touched:

## Hypothesis

- Expected bad behavior:
- Why it should happen:
- What invariant should break:

## Falsifiers

- What result would prove this theory wrong?
- What assumption is most fragile?
- What environment dependency could create a false signal?

## Reproduction Plan

- Test type: unit / integration / fork / live deployed-code match
- Setup:
- Action:
- Assertion:
- Required env:

## Evidence

- File references:
- Test name:
- Logs or revert:
- Before / after balances:
- Before / after state:

## Impact Boundary

- Best honest severity right now:
- Maximum claim supported by current evidence:
- What is still missing before report quality:

## Decision

- Status: `keep` / `kill` / `out of scope` / `low impact`
- Next step:
- Fix pattern if real:

---

## Short Example

- Claim:
  `I think bypassing an entire selected redemption range causes redeemFromQueue() to revert because the contract still tries to redeem zero shares.`
- Falsifier:
  `If the function advances the queue cleanly without redeeming shares, the theory is wrong.`
- Repro:
  `Queue two requests, bypass both, call redeemFromQueue(), assert revert or clean advance.`
