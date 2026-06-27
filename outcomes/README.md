# Outcome Ledger

The outcome ledger connects ANCHOR benchmark evidence to real-world report handling.

Use it to record when a benchmark artifact becomes public and when a real report moves through review.

## Commands

```bash
anchor outcome history --limit 10
anchor outcome record --stage report_submitted --target enzyme --run-id <run_id> --report-id <external_id> --note "submitted with full PoC"
```

## Suggested stages

- `benchmark_published`
- `report_submitted`
- `triaged`
- `accepted`
- `rejected`
- `patched`
- `merged`

The append-only ledger file is stored at `outcomes/ledger.jsonl`.
