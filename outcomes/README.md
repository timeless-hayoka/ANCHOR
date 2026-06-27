# Outcome Ledger

The outcome ledger is where ANCHOR learns from what happened after the benchmark or hunt.

It closes the loop:

```text
Benchmark -> finding -> PR/report -> outcome -> lesson -> strategy update
```

## Commands

```bash
anchor outcome add --type finding --target enzyme --status accepted --evidence benchmarks/damn-vulnerable-defi/runs/.../README.md --lesson "explicit reproduction survives review" --report-id immunefi-123
anchor outcome history --limit 10
anchor outcome summary --limit 5
```

## Structured fields

Each entry can track:

```json
{
  "type": "benchmark | pr | issue | finding",
  "target": "solmate",
  "status": "open | published | triaged | accepted | rejected | patched | merged",
  "evidence": "artifact path, run id, PR URL, issue URL, or report link",
  "lesson": "what ANCHOR learned"
}
```

Optional linkage fields:

- `run_id`
- `case_id`
- `report_id`
- `note`

## Suggested usage

- Use `benchmark` when a benchmark artifact becomes part of the public record.
- Use `finding` when a real hunt lead becomes a submitted report or receives a decision.
- Use `issue` for bug reports or tracker entries.
- Use `pr` for code contributions and fixes that merge upstream.

## Ledger file

The append-only ledger file is stored at `outcomes/ledger.jsonl`.
