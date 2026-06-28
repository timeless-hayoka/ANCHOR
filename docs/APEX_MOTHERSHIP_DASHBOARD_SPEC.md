# ANCHOR Dashboard Spec

This spec defines the dashboard ANCHOR should use if it adopts the useful operator patterns from Apex Mothership.
The goal is to show proof-gated progress, not to imitate a generic security command center.

## Purpose

The dashboard should answer four questions quickly:

- What is running now?
- What reproduced?
- What failed to reproduce?
- Where is the evidence stored?

## Information Architecture

### Top Level

- Run status strip
- Current benchmark family
- Live event stream
- Evidence bundle state
- Storage health
- AI summary panel

### Primary Views

#### 1. Benchmark Overview

Shows the active benchmark family and its current run.

Widgets:

- total cases
- passed cases
- failed cases
- timed out cases
- queued cases
- published vs development runs

#### 2. Case Timeline

Shows the lifecycle of each case in the proof gate.

States:

- signal detected
- hypothesis formed
- evidence collected
- reproduction attempted
- reproduced
- rejected
- archived

#### 3. Evidence Stream

A live feed of material that can be cited later.

Show:

- detector findings
- run ids
- artifact paths
- reproduction notes
- signed bundle status

#### 4. Storage View

A map of where the evidence is retained.

Show:

- benchmark artifact path
- evidence bundle path
- outcome ledger path
- archive location
- portable SSD status if mounted

#### 5. AI Review Panel

A helper panel that can summarize evidence, compare runs, and draft next steps.

Hard rule:

- AI can summarize
- AI can compare
- AI cannot promote a claim without proof

## Visual Priorities

The dashboard should visually emphasize:

- current run status
- whether evidence is signed
- whether reproduction succeeded
- whether the result is published or still development-tier

Do not emphasize flashy command-center styling over clarity.

## Data Model

The dashboard should consume a small status payload with fields like:

- `benchmark_id`
- `run_id`
- `target`
- `status`
- `case_counts`
- `evidence_paths`
- `storage_health`
- `latest_event`
- `ai_summary`

## Suggested Layout

```text
+--------------------------------------------------------------+
| Status strip | benchmark id | run id | storage | publication |
+----------------------+----------------------+----------------+
| Overview             | Evidence Stream      | AI Review      |
| Case Timeline        | Storage View         | Notes          |
+--------------------------------------------------------------+
```

## Acceptance Criteria

The dashboard is useful when a researcher can answer these in under 30 seconds:

- What benchmark family is active?
- How many cases passed, failed, or timed out?
- Where are the signed artifacts?
- What changed since the last run?

## Integration Notes

This dashboard spec should be implemented on top of ANCHOR's existing proof gate and benchmark history, not as a separate control plane.
