# Cloud & Local Architecture

## Principles

1. **Local-first default** — benchmarks, SARIF processing, ledger writes, and dashboard run on operator hardware unless explicitly routed elsewhere.
2. **Explicit cloud opt-in** — remote LLM, remote storage, or shared dashboards require env flags and documented data boundaries.
3. **Modular knowledge** — reference docs live in `knowledge/` and are retrieved by slug; they are not embedded wholesale in prompts.
4. **Single pipeline spine** — `anchor_sarif` normalizes tool output; Trinity/Forge/Council sit around it, not as parallel products.
5. **Archive over chat** — durable artifacts (ledger, benchmark runs, signed bundles) outrank ephemeral model transcripts.

## ANCHOR implementation map

| Concern | Module / path | Notes |
| --- | --- | --- |
| Operator CLI | `anchor_cli.py` | Subcommands for benchmark, outcome, sarif, knowledge |
| Live dashboard | `anchor_server.py` | FastAPI + static dashboard; SSE for runs |
| Evidence storage | `anchor_storage.py` | Manifest + evidence dir layout |
| Work queue | `anchor_work_queue.py` | Repo-owned prioritized tasks |
| Outcome ledger | `outcomes/ledger.jsonl` | Append-only promotion history |
| Knowledge retrieval | `knowledge_provider.py` | Structured doc lookup |

## Cloud boundaries (when used)

- **LLM calls** — hypothesis rewrite, cluster summaries only; never auto-promote from model text alone.
- **Object storage** — optional mirror of published benchmark tiers; development runs stay local by default.
- **Shared review** — export signed bundles from vault; do not sync raw tool stderr by default.

## Storage routing

```text
signal / SARIF / notes
  -> normalize (local)
  -> cluster + score (local)
  -> validate / proof gate (local Forge path)
  -> ledger + vault archive
  -> optional cloud mirror (published tier only)
```

## Environment hooks

- `ANCHOR_PROJECT_ROOT` — repo root for scripts and knowledge
- `ANCHOR_DATA_ROOT` / vault paths — external HDD or AnchorVault mirror (see Drift `storage.env`)

## Anti-patterns

- Treating cloud LLM output as ledger-ready without validator bridge
- Duplicating knowledge in prompts instead of `KnowledgeProvider.search()`
- Collapsing Trinity analysis and Forge proof into one undifferentiated step
