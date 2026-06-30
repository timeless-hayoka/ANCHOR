# ANCHOR Knowledge Corpus

Structured, implementation-focused reference material for ANCHOR operators, Trinity, and automation.

## Design rules

- **Retrieve, don't stuff** — agents call `KnowledgeProvider` for the slice they need; avoid dumping the whole corpus into prompts.
- **One concept per file** — keep topics modular so they can evolve independently.
- **Evidence-first** — documents describe schemas, gates, and workflows; they do not replace proof.
- **Repo-owned** — this directory is versioned with ANCHOR; vault copies are optional mirrors.

## Topics

| File | Focus |
| --- | --- |
| `cloud_architecture.md` | Local-first boundaries, storage routing, cloud optional paths |
| `sarif.md` | SARIF ingest, normalize, dedup, cluster pipeline |
| `evidence_models.md` | Finding schema, outcome ledger, promotion states |
| `attack_graphs.md` | Investigation graph nodes/edges and correlation |
| `visualization.md` | Cluster viz, dashboard telemetry surfaces |
| `zero_trust.md` | Validator bridge, confidence, proof-gated promotion |
| `ui_patterns.md` | CLI commands, work queue, operator UX |
| `development_backlog.md` | Prioritized next builds |

## Usage

```bash
./anchor knowledge list
./anchor knowledge show sarif
./anchor knowledge search "confidence scoring"
./anchor knowledge refs --subsystem sarif
```

HTTP (when `anchor_server` is running):

- `GET /api/knowledge`
- `GET /api/knowledge/{slug}`
- `GET /api/knowledge/search?q=...`

Python:

```python
from knowledge_provider import KnowledgeProvider

kp = KnowledgeProvider()
doc = kp.get("evidence_models")
hits = kp.search("promotion gate", limit=5)
```

## Adding material

1. Add or edit a `.md` file in this directory.
2. Register it in `manifest.json` (`slug`, `subsystems`, `tags`).
3. Run `pytest tests/test_knowledge_provider.py`.

## Archival JSON (training / detectors / scenarios)

Runtime artifacts from BugBot or trainers are written under:

| Directory | Purpose |
| --- | --- |
| `training/` | Complete training run snapshots |
| `detectors/` | Per-detector result archives |
| `scenarios/` | Curated scenario definitions (stable ids) |
| `analysis/` | Immutable protected analysis run records |

Use `knowledge.pipeline.KnowledgePipeline` (respects `ANCHOR_ROOT`). These files are separate from manifest-registered markdown topics—retrieve reference docs via `KnowledgeProvider`, not by stuffing JSON into prompts.

```python
from knowledge.pipeline import KnowledgePipeline

pipeline = KnowledgePipeline()
result = pipeline.archive_scenario({"id": "reentrancy-basic", "steps": []})
if result.success:
    print(result.path)
else:
    print(result.error)
```
