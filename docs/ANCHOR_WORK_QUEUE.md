# ANCHOR Work Queue

This file is the living implementation queue for the ANCHOR project.

The system already has:

- benchmark history and trend analysis
- outcome ledger recording
- proof-gated hunt planning inputs
- local run server and SSE event streaming

The remaining work is to keep the hunt process explicit, reproducible, and easy to review.

## Current priorities

1. Expand the hunt planner with target-specific heuristics.
2. Add more target notes so the planner has real scope input.
3. Keep the proof gate strict: no claim promotion without a fork repro.
4. Add regression coverage for hunt-plan output as new target types land.

## Done when

- every serious target has a structured hunt plan
- the plan names what to hunt for, how to test it, and what kills the theory
- the plan can be consumed by the CLI and the server
- the evidence bundle and repro path remain the promotion boundary
