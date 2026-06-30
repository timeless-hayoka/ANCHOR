# ANCHOR Philosophy

ANCHOR exists because security research produces too many **plausible** claims and too few **reproducible** ones.

Most tools answer:

> What might be wrong?

ANCHOR answers:

> What can actually be reproduced?

Every promoted finding must pass the Proof Gate before it enters the knowledge corpus, influences strategy, or becomes part of a public benchmark claim.

## The spine

```text
Evidence First
      ↓
Proof Gate
      ↓
Regression
      ↓
Outcome
      ↓
Knowledge
      ↓
Strategy
```

| Stage | Question |
| ----- | -------- |
| Evidence First | What did the tools or humans observe? |
| Proof Gate | Can we reproduce impact in an authorized environment? |
| Regression | What changed since the last published run? |
| Outcome | What did we learn from pass, fail, timeout, or false positive? |
| Knowledge | What durable reference material should operators retrieve later? |
| Strategy | What should we work on next, given proof—not vibes? |

## Design commitments

**One source of truth.** Trend math lives in `anchor_trends.py`. Strategy consumes it. Dashboards and reports render snapshot fields—they do not recompute rates, deltas, or rankings in the browser.

**Benchmarks before claims.** Published artifacts in `benchmarks/index.json` are the comparison baseline. Local development runs stay separate until explicitly published.

**Retrieve, don't stuff.** Structured knowledge (`knowledge/*.md`, archival JSON under `knowledge/training/`, etc.) is queried by slug or search. Agents and trainers pull slices; they do not paste the whole corpus into prompts.

**Local-first.** ANCHOR runs on your machine with your authorized targets. Cloud backends are optional; evidence and signing stay under your control.

**Preserve failure.** A failed reproduction is data. ANCHOR keeps the trail from signal → hypothesis → attempt → outcome so reviewers see what was tried, not just what succeeded.

## What ANCHOR is not

- Not a scanner replacement — it orchestrates and gates evidence from scanners and humans.
- Not a vibes dashboard — numbers on the dashboard come from canonical backend modules.
- Not a legal chain-of-custody product — signatures are tamper-evident locally, not courtroom guarantees.

## For contributors

Read [CONTRIBUTING.md](../CONTRIBUTING.md) for workflow and [docs/REPRODUCTION.md](REPRODUCTION.md) for the credibility gate: a clean machine should reach the same class of benchmark artifact ANCHOR publishes.

When in doubt, ask: *Does this change help someone reproduce proof, or does it only make a claim louder?*
