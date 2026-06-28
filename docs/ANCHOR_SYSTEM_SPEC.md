# ANCHOR Unified System Spec

ANCHOR is one orchestrated, proof-gated research system.

The goal is not to split the project into multiple products or models. The goal is to keep one operator workflow, one evidence path, one output format, and one dashboard/CLI that expose a shared internal pipeline.

## System Goals

- one orchestrated ANCHOR pipeline
- multiple internal modules under the same repo
- one output format for findings, evidence, and strategy
- one UI/CLI that shows the combined result
- one outcome ledger that records what was actually proved

## Canonical Data Flow

```text
source notes / tool output / benchmark result
-> normalize
-> cluster
-> validate
-> rewrite into future-state hypotheses when useful
-> simulate current vs future protocol assumptions
-> score evidence and economic relevance
-> promote or reject
-> archive to ledger and vault
-> surface in CLI and dashboard
```

The key rule is simple:

- hypothesis generation can be creative
- promotion to the ledger must still be proof-gated

## Unified Module Tree

```text
ANCHOR
├── anchor_cli.py
├── anchor_server.py
├── anchor_strategy.py
├── anchor_trends.py
├── anchor_storage.py
├── anchor_scripts.py
├── anchor_sarif/
│   ├── parser.py
│   ├── normalizer.py
│   ├── deduplicator.py
│   ├── semantic_clusterer.py
│   ├── fp_heuristics.py
│   ├── pipeline.py
│   ├── future_state.py
│   ├── economic_context.py
│   ├── universe.py
│   ├── assumptions.py
│   ├── mev_lifecycle.py
│   ├── drift.py
│   ├── incentive_surface.py
│   ├── research_loop.py
│   └── validator_bridge.py
├── hunts/
├── knowledge/
├── benchmarks/
├── outcomes/
└── docs/
```

The existing SARIF pipeline remains the core analysis spine.

The new modules are not separate products. They are staged capabilities inside the same spine:

- `future_state.py` rewrites findings into future protocol assumptions
- `economic_context.py` scores how economically sensitive a finding is
- `universe.py` compares current-world and future-world outcomes
- `drift.py` measures whether a finding shifts meaning across models
- `assumptions.py` extracts implicit protocol assumptions
- `mev_lifecycle.py` tracks how MEV techniques evolve over time
- `incentive_surface.py` maps the adversarial search space
- `research_loop.py` turns those signals into ranked hunt work
- `validator_bridge.py` passes only high-signal candidates to proof and review

## Internal Stages

### 1. Pattern Mining

Purpose:

- mine historical bug classes
- turn old lessons into reusable patterns
- search for similar shapes in new code

Outputs:

- pattern cards
- target tags
- candidate hypotheses

### 2. Semantic Clustering

Purpose:

- group similar findings
- separate repeated noise from repeated signal
- track semantic drift over time

Outputs:

- cluster IDs
- cluster summaries
- similarity deltas

### 3. Validation Bridge

Purpose:

- decide whether a finding deserves more work
- attach proof-gate status
- keep false positives from polluting the ledger

Outputs:

- promoted / review / rejected
- evidence requirements
- proof status

### 4. Differential Testing

Purpose:

- compare implementations, versions, forks, or simulated worlds
- identify divergence as a signal

Outputs:

- mismatch notes
- expected-vs-actual deltas
- version-change risk markers

### 5. Negative-Space Testing

Purpose:

- ask what should never happen
- test impossible callers, transitions, and states

Outputs:

- forbidden-path checks
- invariant violations
- exclusion notes

### 6. Economic and MEV Scoring

Purpose:

- score incentive-sensitive findings
- evaluate profit, griefing, censorship, and ordering assumptions

Outputs:

- economic relevance scores
- MEV sensitivity scores
- future-impact labels

### 7. Hunt Workflow UI and CLI

Purpose:

- make the operator see the same story everywhere
- show current hunt, current evidence, and next recommendation

Outputs:

- CLI summaries
- dashboard panels
- hunt queue entries

## Current In-Repo Surface

These are already the main ANCHOR entrypoints:

- `anchor_cli.py`
- `anchor_server.py`
- `anchor_sarif/`
- `anchor_strategy.py`
- `anchor_trends.py`
- `anchor_storage.py`
- `docs/METHODOLOGY.md`
- `docs/PROOF_GATE.md`
- `docs/EVIDENCE_LIFECYCLE.md`
- `docs/ANCHOR_KNOWLEDGE_INGESTION.md`
- `docs/APEX_MOTHERSHIP_INTEGRATION.md`

## Implementation Backlog

### Phase 1: Core Hunt Intelligence

- add `anchor_sarif/future_state.py`
- add `anchor_sarif/economic_context.py`
- add `anchor_sarif/validator_bridge.py`
- add tests for each new module
- extend the SARIF pipeline to accept optional future-state rewriting

### Phase 2: Simulation and Drift

- add `anchor_sarif/universe.py`
- add `anchor_sarif/drift.py`
- add `anchor_sarif/assumptions.py`
- add tests for current-world vs future-world comparisons
- add tests for drift scoring and assumption extraction

### Phase 3: Research Expansion

- add `anchor_sarif/mev_lifecycle.py`
- add `anchor_sarif/incentive_surface.py`
- wire economic scoring into the hunt queue
- add synthetic finding support for simulation outputs

### Phase 4: Operator Surfacing

- add a single hunt summary to the CLI
- add hunt status to the dashboard snapshot
- show future relevance and validation state in the UI
- keep benchmark and hunt views in the same operator console

### Phase 5: Feedback Loop

- promote confirmed findings into the ledger
- feed accepted lessons back into pattern mining
- rank future hunts using prior proof results
- keep the system one project, not a pile of disconnected experiments

## Design Rules

- One repo.
- One operator story.
- One evidence format.
- One proof gate.
- One ledger.
- Many internal modules, all subordinate to the same workflow.

## Why This Matters

ANCHOR gets stronger when it can do two things at once:

- describe the current bug surface
- model how that surface changes under new protocol rules

That is still one system. The difference is only that the system now has a richer internal pipeline.
