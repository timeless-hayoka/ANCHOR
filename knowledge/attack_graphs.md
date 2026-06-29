# Investigation Graphs

## Concept

An **investigation graph** links signals, findings, clusters, reproduction attempts, and outcomes so operators see *why* a hunt item ranked high—not just that a tool fired.

## Node types

| Node | Source | Key fields |
| --- | --- | --- |
| `signal` | Tool raw hit | tool, rule_id, location |
| `finding` | Normalized Finding | dedup_key, level |
| `cluster` | semantic_clusterer | cluster_id, summary |
| `hypothesis` | future_state rewrite | assumption label, drift score |
| `repro` | Forge / benchmark | pass/fail, run_id |
| `outcome` | ledger.jsonl | status, lesson |

## Edge types

- `duplicate_of` — deduplicator merge
- `similar_to` — embedding neighbor (cluster)
- `depends_on` — code_flow / call path
- `validated_by` — repro succeeded
- `refuted_by` — repro failed or council reject
- `promoted_to` — ledger acceptance

## Workflow

1. Ingest SARIF → create `signal` + `finding` nodes.
2. Cluster → add `cluster` node; link members with `similar_to`.
3. Validator bridge → attach confidence to finding node metadata.
4. On repro attempt → add `repro` node; edge `validated_by` or `refuted_by`.
5. On ledger write → add `outcome` node; edge `promoted_to`.

## Implementation status

- **Today**: implicit via SQLite findings DB + ledger links (`links.benchmark`, `links.artifact`).
- **Next**: explicit graph export JSON for dashboard overlay (see `development_backlog.md`).

## Query patterns

- "Show all findings in cluster X that lack `validated_by`."
- "List hypotheses with high economic score but no repro node."
- "Timeline: signals → repro → outcome for case Y."

## Storage sketch

```json
{
  "nodes": [{"id": "f-abc", "kind": "finding", "refs": {"dedup_key": "..."}}],
  "edges": [{"from": "f-abc", "to": "c-12", "kind": "similar_to", "weight": 0.91}]
}
```

Keep graph derived from canonical stores (findings DB + ledger)—do not fork truth into a second database without sync rules.
