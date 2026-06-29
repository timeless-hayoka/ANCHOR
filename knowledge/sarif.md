# SARIF Pipeline

## Purpose

Turn heterogeneous static-analysis output into one **Finding** model, then deduplicate, cluster, and feed the research loop.

## Pipeline stages

```text
.sarif / tool JSON
  -> parser.Finding
  -> normalizer (stable fields + dedup_key)
  -> deduplicator
  -> semantic_clusterer
  -> fp_heuristics + validator_bridge
  -> research_loop ranked work
```

## Core types

- **`Finding`** (`anchor_sarif/parser.py`) — tool, rule_id, level, message, file_path, line, snippet, code_flows, properties.
- **`dedup_key`** — stable hash for cross-run deduplication.
- **`ValidationDecision`** — promote | review | reject with confidence and economic scores.

## CLI entrypoints

```bash
./anchor sarif process findings.sarif --db anchor_sarif_findings.db
./anchor sarif research findings.sarif --future-state "ePBS + inclusion lists"
./anchor sarif visualize --output sarif_clusters.html
```

## Adapter pattern

Tool-specific quirks live in `anchor_sarif/adapters/` (Slither, Mythril, Aderyn, Halmos). Adapters emit SARIF-shaped or normalized payloads; the parser stays tool-agnostic.

## Implementation notes

- Persist clustered findings in SQLite when `--db` is set; enables tune/visualize without re-parse.
- Semantic clustering is optional LLM summarization (`--llm`); default is embedding-only.
- Benchmark gate: `benchmarks/sarif-known-findings/` regression corpus for parser + cluster stability.

## Failure handling

- Malformed SARIF: skip run with logged path, do not partial-promote.
- Empty runs: still write benchmark.json with zero counts for trend comparison.
