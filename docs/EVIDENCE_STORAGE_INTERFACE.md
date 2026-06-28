# ANCHOR Evidence Storage Interface

This document defines the shared storage contract for benchmark artifacts, signed evidence, and outcome records.

## Purpose

The interface should answer:

- where an artifact belongs
- how it is named
- how it is linked to a run
- how it is promoted into history

## Storage Tiers

### 1. Active Run Storage

Stores the current run's working artifacts.

Typical contents:

- raw logs
- detector output
- case notes
- reproduction traces
- temporary summaries

### 2. Published Benchmark Storage

Stores the curated artifacts for history and comparison.

Typical contents:

- published README
- benchmark JSON
- signed evidence references
- summary tables
- lessons learned

### 3. Outcome Ledger Storage

Stores the durable chain of what ANCHOR learned.

Typical contents:

- outcome events
- report links
- benchmark links
- lessons
- publication status

### 4. Archive Storage

Stores interrupted or superseded runs for traceability.

## Required Artifact Fields

Every stored artifact should carry:

- `benchmark_id`
- `run_id`
- `target`
- `stage`
- `status`
- `created_at`
- `artifact_type`
- `artifact_path`
- `signature_state`

## Recommended Layout

```text
benchmarks/
  <family>/
    runs/
      <run_id>/
        README.md
        benchmark.json
        logs/
        artifacts/
        evidence/

outcomes/
  ledger.jsonl

docs/
  ANCHOR_VAULT.md
```

## Storage Contract

The storage layer should support:

- append-only ledger entries
- stable artifact paths
- promotion from development to published tier
- easy cross-linking between benchmark and outcome data
- reproducible references for later review

## Promotion Rule

A run becomes published only when:

- its reproduction is clear
- its evidence is retained
- its summary is reviewable
- its outcome record is linked

## Interface Consumers

This interface should be consumable by:

- CLI history commands
- dashboard views
- publication workflows
- evidence review tools
- archive tools

## Safety Boundary

Never treat a path as a result by itself.
The result is the combination of the artifact, the evidence, and the verified reproduction.
