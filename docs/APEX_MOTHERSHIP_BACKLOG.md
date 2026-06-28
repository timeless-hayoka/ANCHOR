# Apex Mothership Integration Backlog

This backlog turns the Apex Mothership sibling project into a phased ANCHOR upgrade path.

## Phase 1: Shared Visibility

Goal: make benchmark progress visible in the ANCHOR dashboard.

Tasks:

- define benchmark status payload
- surface case counts and run status
- add evidence path display
- show storage health
- expose published vs development tier

## Phase 2: Evidence Routing

Goal: connect storage, ledger, and benchmark history.

Tasks:

- standardize artifact naming
- link run records to outcome entries
- show archive vs active storage
- expose signed evidence references
- make promotion explicit

## Phase 3: AI Review Assistance

Goal: use AI as a summarizer and comparator, not as an authority.

Tasks:

- summarize run deltas
- compare benchmark results
- draft next-step notes
- highlight missing evidence
- keep reproduction as the gate

## Phase 4: Script Registry

Goal: safely expose approved helper scripts.

Tasks:

- create allowlist manifest
- add registry audit logging
- surface approved helpers in the dashboard
- add authorization markers for higher-risk helpers
- separate benchmark helpers from live-target utilities

## Phase 5: Operator UX

Goal: make the dashboard feel intentional and clear.

Tasks:

- build a single status strip
- add evidence stream timeline
- add storage summary cards
- add publication state labels
- keep ANCHOR visually dominant as the flagship

## Phase 6: Hardening and Review

Goal: make the new surface trustworthy.

Tasks:

- add focused tests for payload rendering
- add tests for ledger promotion
- validate registry authorization checks
- verify storage path correctness
- keep the proof gate intact

## Definition of Done

This integration is done when:

- benchmark runs are visible in the dashboard
- artifacts are linked to evidence and outcomes
- approved scripts are listed and audited
- AI only assists with review
- ANCHOR still remains the flagship evidence gate
