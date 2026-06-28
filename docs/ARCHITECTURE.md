# Architecture

ANCHOR separates reasoning, validation, governance, and retained evidence.

For the unified internal module tree and end-to-end workflow, see [ANCHOR_SYSTEM_SPEC.md](ANCHOR_SYSTEM_SPEC.md).

## Components

### Product: ANCHOR

ANCHOR is the operator-facing workflow and evidence system.

Responsibilities:

- coordinate hunts
- track case state
- stream live events
- export evidence bundles
- keep the methodology consistent

### Reasoning: Trinity

Trinity is the analysis layer.

Responsibilities:

- summarize leads
- compare mechanisms
- explain severity reasoning
- help draft reports
- stay subordinate to the evidence gate

Trinity can suggest. It cannot promote a claim without proof.

### Validation: Forge

Forge is the reproduction gate.

Responsibilities:

- run proofs of concept
- validate exploitability
- enforce complete reproduction paths
- reject claims that fail to execute

### Governance: Council

Council is the review layer.

Responsibilities:

- judge whether evidence is complete
- decide whether impact framing is justified
- prevent overclaiming
- approve report-ready findings

### Knowledge: Vault

Vault is the retained evidence and learning layer.

Responsibilities:

- archive cases
- preserve signed bundles
- track benchmark outcomes
- retain lessons learned

## System flow

```text
signal
-> hypothesis
-> tool evidence
-> reproduction attempt
-> council review
-> report-ready archive
```

## Design principles

- local-first by default
- explicit scope discipline
- reproducibility over rhetoric
- evidence before severity language
- archived outcomes over ephemeral chat

## Why this separation matters

A lot of security tooling collapses analysis and proof into the same step.

ANCHOR does not.

That separation is what keeps the system honest:

- Trinity can be useful without being authoritative.
- Forge can fail a claim even when the idea sounds plausible.
- Council can reject sloppy framing even when a test reproduces something interesting.
- Vault keeps the trail reviewable later.
