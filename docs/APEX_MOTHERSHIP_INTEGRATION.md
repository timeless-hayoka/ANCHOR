# Apex Mothership Integration Plan

This note turns the Apex Mothership sibling project into a concrete set of ANCHOR integration targets.
The goal is to borrow useful operator surfaces without weakening ANCHOR's proof-gated model.

## Source Project Summary

Apex Mothership is a private Python/FastAPI + React security command center. The current shape is:

- FastAPI backend
- React dashboard frontend
- live telemetry via WebSockets
- AI bridge to Gemini
- SSD-backed mission/report storage
- script discovery for local `.py`, `.sh`, and `.js` tooling
- startup script that expects a mounted portable SSD

## What ANCHOR Should Borrow

### 1. Live Ops Dashboard

Bring over the useful visual pattern, not the command-center framing.

ANCHOR should expose:

- benchmark run status
- case lifecycle state
- live evidence stream
- detector / reproduction progress
- storage health for signed artifacts

### 2. Telemetry Panel

The Apex telemetry panel is useful as a pattern for:

- CPU load
- memory pressure
- disk usage
- network activity
- local service health

In ANCHOR, this belongs in the demo and server surfaces as operational visibility for benchmark runs.

### 3. AI Bridge

The Gemini bridge is worth keeping, but only in ANCHOR's proof-gated shape:

- summarize evidence
- explain detector output
- draft hypotheses
- compare benchmark runs
- never replace reproduction evidence

### 4. SSD Vault Routing

The portable SSD routing idea is useful because ANCHOR already values durable traces.

ANCHOR should keep:

- signed artifacts
- benchmark JSON
- run notes
- evidence bundles
- outcome ledger exports

### 5. Script Registry

The script-discovery idea is useful if it becomes a guardrailed registry:

- allowlisted analysis scripts
- benchmark helpers
- local transforms
- explicit authorization for any action that touches live systems

## What ANCHOR Should Not Import Directly

- one-click execution of broad offensive tools without scope gates
- ad hoc kernel tuning as a default requirement
- unreviewed command execution paths
- UI language that implies command-and-control rather than evidence-gated research

## Integration Milestones

### Milestone 1: Shared Observability

Expose benchmark run telemetry in ANCHOR's dashboard and server pages.

### Milestone 2: Evidence Routing

Link run artifacts, signed evidence, and outcome ledger entries into the same storage flow.

### Milestone 3: AI-Assisted Review

Use the AI bridge to summarize and compare evidence, but keep the final judgment tied to reproduction.

### Milestone 4: Guardrailed Script Registry

Add a registry for local helper scripts that can be used in benchmark workflows and authorized research.

### Milestone 5: Unified Operator UX

If a dashboard is retained, it should present ANCHOR as the flagship and Apex Mothership as a supporting operator surface.

## Recommended Ownership Split

- ANCHOR: proof gate, benchmark corpus, evidence ledger, publication history
- Apex Mothership ideas: telemetry, dashboard layout, script registry, SSD vault routing, AI assistance
- Shared principle: evidence before claims

## Practical Next Steps

1. Map ANCHOR benchmark runs into a dashboard panel.
2. Add an evidence-storage view that shows where artifacts live.
3. Add a script registry abstraction for authorized local helpers.
4. Keep all experimental scanning behind explicit scope checks.
## Linked Artifacts

- [ANCHOR Dashboard Spec](APEX_MOTHERSHIP_DASHBOARD_SPEC.md)
- [Script Registry Design](SCRIPT_REGISTRY_DESIGN.md)
- [Evidence Storage Interface](EVIDENCE_STORAGE_INTERFACE.md)
- [Implementation Backlog](APEX_MOTHERSHIP_BACKLOG.md)

