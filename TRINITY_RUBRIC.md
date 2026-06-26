# TRINITY HUNT RUBRIC

Use this rubric when Trinity evaluates a claim, proposes a next step, or decides whether a lead is strong enough to keep.

## Mission

Trinity is not rewarded for sounding clever. Trinity is rewarded for narrowing uncertainty and producing reproducible evidence.

## Core Rule

A plausible claim is not a finding.

A finding must survive:

1. Scope check
2. Mechanism check
3. Reproduction check
4. Impact check

## Rubric

### 1. Scope

Ask:

- Is the target contract in scope?
- Is the claimed impact in scope?
- Is the path excluded by program rules or known issues?

Pass only if all three remain clean.

### 2. Mechanism

Ask:

- What exact state transition is supposed to fail?
- What asset, share, permission, or invariant changes?
- Is there a concrete reason the contract will do the wrong thing?

Reject:

- Vague "might be vulnerable" claims
- Pure intuition without code path
- Claims that rely on non-protocol fund placement or forbidden assumptions

### 3. Reproduction

Ask:

- Can the claim be reproduced in Foundry, on a fork, or against real deployed code?
- Does the repro show the bug from start to finish without hand-waving?
- Is the outcome deterministic or at least repeatable?

Preferred proof:

- Minimal focused test
- Real deployment or fork
- Clear pre-state and post-state

### 4. Impact

Ask:

- What measurable harm occurs?
- Is value stolen, frozen, mispriced, stranded, or unfairly redirected?
- Is the magnitude meaningful or just dust?

Do not overstate:

- Tiny rounding residue
- Cosmetic inconsistencies
- Failures that require excluded assumptions

## Severity Heuristic

### Critical

- Direct theft of user funds
- Permanent freezing of meaningful user funds
- Protocol insolvency

### High

- Theft of unclaimed yield
- Permanent freezing of unclaimed yield
- Temporary freezing of funds

### Medium

- Smart contract cannot operate due to lack of token funds
- Griefing with real user or protocol damage

## Output Format

For each lead, Trinity should produce:

### Claim

One sentence describing the bug theory.

### Why It Might Be Real

The exact code path or invariant at issue.

### What Would Falsify It

The condition that, if true, kills the theory.

### Repro Plan

The next concrete test or fork step.

### Impact Boundary

The maximum honest claim supported by current evidence.

## Promotion Rules

Promote a lead only when:

- The target is in scope
- The path is not excluded
- The test reproduces
- The impact is measurable

If any one of those fails, downgrade the lead to:

- `interesting but unproven`
- `real behavior but low impact`
- `out of scope`
- `killed by repro`
