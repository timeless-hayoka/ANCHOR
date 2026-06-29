# CLI & Dashboard Patterns

## CLI philosophy

- **Repo-owned commands** — `./anchor` from ANCHOR root; no hidden global state.
- **Subcommand namespaces** — `benchmark`, `outcome`, `sarif`, `work`, `knowledge`, `strategy`.
- **Human-readable defaults** — tables to stdout; `--json` where scripts need machine output (knowledge search).

## High-value operator flows

```bash
# Run benchmark
./anchor benchmark dvd phase1

# Promote run to published tier
./anchor benchmark publish <run-id>

# Record real-world outcome
./anchor outcome add --type finding --status accepted --title "..." --link-benchmark <run-id>

# Inspect prioritized work
./anchor work queue

# Pull architecture reference without opening docs/
./anchor knowledge search "promotion gate"
```

## Work queue integration

`anchor_work_queue.py` renders markdown queue synced with strategy output—dashboard and CLI share the same file.

## Dashboard operator loop

1. Start server: `python anchor_server.py` (or systemd user unit).
2. Open dashboard → Live Run or benchmark trigger.
3. Watch SSE events; cross-check artifact paths on disk.
4. Record outcome in ledger when external submission completes.

## Error presentation

- Fail closed on missing manifest or unknown benchmark target.
- SARIF commands degrade gracefully when optional deps missing (`HAS_SARIF` flag in CLI).
- Knowledge commands never fetch network—local corpus only.

## Future UI hooks

- Graph overlay panel (investigation graph export).
- Knowledge sidebar fed by `GET /api/knowledge/search` not static prompt injection.
