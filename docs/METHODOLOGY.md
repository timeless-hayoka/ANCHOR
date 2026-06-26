# Methodology

ANCHOR is not a claim generator. It is an evidence workflow.

## Sequence

1. Scope confirmation
2. Hypothesis creation
3. Evidence collection
4. Reproduction
5. Council review
6. Report generation
7. Archive

## 1. Scope confirmation

Before any hunt is treated as meaningful, the target must be confirmed as authorized.

Checks include:

- program or client scope
- allowed assets and impacts
- prohibited test actions
- required proof-of-concept standard
- whether the current hypothesis is already excluded or known

If scope is unclear, the hunt pauses.

## 2. Hypothesis creation

Every serious lead is written as a falsifiable claim.

A good hypothesis states:

- the contract or component
- the suspected mechanism
- the expected impact
- the state or call sequence required
- what evidence would disprove it

The goal is to avoid vague "this looks scary" hunting.

## 3. Evidence collection

Evidence begins before reproduction succeeds.

Evidence can include:

- traces
- state snapshots
- tool outputs
- benchmark classifications
- source references
- accounting diffs
- call path notes

At this stage ANCHOR still treats the lead as provisional.

## 4. Reproduction

Reproduction is the gate.

A claim is not promoted until a complete proof of concept demonstrates the behavior on:

- a local fork of the live deployment, or
- deployed production-equivalent code in an authorized environment

Mock-only proofs, incomplete snippets, or hand-wavy scenarios do not pass.

## 5. Council review

Council review asks:

- is the mechanism real
- is the PoC complete
- is the impact in scope
- is the severity justified
- is there an alternative explanation
- is the issue already known or excluded

A reproduced bug can still be rejected if the framing is wrong.

## 6. Report generation

A report becomes ready when it contains:

- precise summary
- impact statement
- affected code path
- exact reproduction steps
- proof-of-concept command or test
- remediation guidance
- evidence bundle references

## 7. Archive

The archive preserves:

- the hypothesis
- the test history
- final classification
- signed evidence bundle
- lessons learned

This matters for benchmark quality, regression checks, and trust.

## Status ladder

The working ladder is:

- `signal`
- `hypothesis`
- `repro_attempted`
- `reproduced_real`
- `council_accepted`
- `report_ready`

Only later stages should be spoken about publicly as findings.
