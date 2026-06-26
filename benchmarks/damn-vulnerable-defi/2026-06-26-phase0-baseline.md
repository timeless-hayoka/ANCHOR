# Damn Vulnerable DeFi Baseline - 2026-06-26

## Status

Phase 0 baseline only.

This record is intentionally narrow: it captures what ANCHOR can support honestly today from repository evidence. It does **not** claim a full ANCHOR-driven Damn Vulnerable DeFi benchmark harness yet.

## Target

Damn Vulnerable DeFi challenge corpus, represented in the current repo by the `DVD Arena` fixture snapshot in the console UI.

## Scope

Authorized local benchmark only. This is not a live bounty target.

## Methodology

This baseline combines two evidence sources:

1. The ANCHOR server's tested demo-run contract, which proves the event pipeline and evidence signing path.
2. The current `DVD Arena` fixture snapshot in the console UI, which records the present challenge outcomes exposed by the repo.

That means this record is useful as a methodology and presentation baseline, not yet as a complete end-to-end benchmark of the DVD corpus through the ANCHOR server.

## Tooling

Verified in repo today:

- FastAPI test client
- SSE event stream
- ed25519 evidence signing
- local fixture-backed console rendering

Planned for full benchmark harness:

- slither
- mythril
- echidna
- medusa
- forge

## Detection results

No ANCHOR-wide detector totals are claimed for DVD yet.

Current repo evidence only shows challenge-level outcome fixtures in the UI:

- `shards`
- `wallet-mining`
- `withdrawal`

## Reproduction results

Current `DVD Arena` fixture snapshot shows:

- `0` solved
- `2` failed
- `1` skipped

Challenge snapshot details:

- `shards`
  - test path: `test/shards/Shards.t.sol`
  - status: `FAILED`
  - rc: `1`
  - duration: `0.306s`
  - note: `Marketplace still has tokens: 0 <= 75000000000000000`
- `wallet-mining`
  - test path: `test/wallet-mining/WalletMining.t.sol`
  - status: `FAILED`
  - rc: `1`
  - duration: `0.384s`
  - note: `No code at user's deposit address: 0 == 0`
- `withdrawal`
  - test path: `test/withdrawal/Withdrawal.t.sol`
  - status: `SKIPPED`
  - rc: `0`
  - duration: `0.0s`
  - note: `Skipped: requires RPC/.env, none present`

## False positives

Not scored yet.

The current baseline does not expose challenge-by-challenge detector claims, so there is no honest false-positive count to publish here.

## False negatives

Not scored yet.

A full false-negative view requires a benchmark harness that compares expected challenge behavior against ANCHOR detections and completed reproductions.

## Lessons learned

- The repo can already demonstrate ANCHOR's evidence workflow cleanly: event stream, ordered ladder events, and signed evidence.
- The DVD section is currently a useful field-deployment mirror, but not yet a fully measured benchmark suite.
- Publishing this baseline now is still valuable because it distinguishes verified infrastructure from benchmark claims that have not been earned yet.
- The next quality step is to move DVD from static fixture presentation to reproducible, server-recorded benchmark runs with retained artifacts.

## Evidence artifacts

Verified today in repo:

- `tests/test_anchor_server.py` verifies:
  - demo run creation
  - SSE event ordering
  - evidence signing
  - replay after cursor
  - ingest path
- `interfaces/static/trinity_hunt.html` contains the current `DVD Arena` fixture snapshot used for this baseline.
- `README_anchor_server.md` documents the live event contract and signing flow that back the ANCHOR methodology.

## Confidence note

This is a trustworthy baseline because it says only what the repo currently proves.

It is not yet the final form of the DVD benchmark story. It is the first auditable step toward it.
