# ANCHOR Knowledge Ingestion Plan

This plan keeps repo mining focused on reusable knowledge, not raw cloning.

## Top 3 repos to mine first

1. `AI-Forge-Protocol`
2. `bounty-bot`
3. `apex-mothership`

These three cover the strongest overlap with ANCHOR right now: proof gating, outcome tracking, dashboard telemetry, and guarded operator workflows.

## What to extract

### AI-Forge-Protocol

Use this repo for:

- validation and scoring flow
- risky-patch blocking logic
- structured audit trails for generated work
- clear pass/fail criteria around proof

Most reusable sources:

- README and architecture notes
- validation pipeline docs
- audit or scoring schema files

### bounty-bot

Use this repo for:

- triage queues
- claim lifecycle tracking
- proof-backed outcome recording
- report and issue state transitions

Most reusable sources:

- README
- issue or claim workflow docs
- any result ledger or status templates

### apex-mothership

Use this repo for:

- dashboard layout ideas
- live telemetry surfaces
- script discovery and helper registry ideas
- SSD or vault-style storage routing

Most reusable sources:

- README
- dashboard or UI docs
- script discovery docs
- storage or routing notes

## Repo-to-subsystem map

| Repo | ANCHOR subsystem it should inform |
| --- | --- |
| `AI-Forge-Protocol` | proof gate, validator scoring, patch admission rules |
| `bounty-bot` | outcome ledger, triage flow, report state machine |
| `apex-mothership` | dashboard, telemetry, script registry, evidence storage UX |

## Clean ingestion checklist

- confirm the repo is readable and relevant before copying anything
- extract docs and schema files first
- skip secrets, keys, caches, and generated artifacts
- store the result as a concise vault note, not a full mirror
- tag each note with the ANCHOR subsystem it supports
- keep one source of truth per concept so the vault does not duplicate itself
- record the repo URL and date of extraction
- add a short lesson about why the material mattered

## Suggested vault note format

- Source repo
- What was extracted
- Why it matters to ANCHOR
- Subsystem affected
- Follow-up action

## Next move

Start with `AI-Forge-Protocol`, then `bounty-bot`, then `apex-mothership`. That order gives ANCHOR the strongest proof-gate knowledge first, then workflow state tracking, then the UI/storage layer.
