# Codex MCP for ANCHOR

This repository ships a small read-only MCP server so Codex can inspect ANCHOR state without guessing.

## What it exposes

- `repo_status` - git state, top-level workspace entries, and latest published benchmark id
- `work_queue` - parsed `docs/ANCHOR_WORK_QUEUE.md`
- `benchmark_latest` - rendered latest published benchmark summary
- `benchmark_compare_source` - source-tool delta for a benchmark run
- `benchmark_history` - rendered benchmark history table

## Run it

```bash
python3 codex_mcp_server.py
```

The server uses stdio, which is the best fit for local Codex workflows.

## Example host config

Do not hand-type an absolute path here — it will break the moment the repo
moves, the environment is renamed, or you register from a different
machine. Instead, generate the config from the repo itself, which resolves
its own location at runtime:

```bash
./scripts/codex_mcp_launcher.py --print-config
```

That prints a `command`/`args`/`cwd` triple computed from `codex_mcp_launcher.py`'s
own path (`Path(__file__).resolve().parents[1]`), so it is always correct for
wherever the repo currently lives — no hardcoded host, username, or
environment name involved.

## Notes

- The server is intentionally read-only.
- It reuses ANCHOR's own parsers and renderers so the MCP view stays aligned with the CLI.
## Launcher helper

The repo also includes a tiny launcher that can print the registration snippet or
register the server through the local Codex CLI:

```bash
./scripts/codex_mcp_launcher.py --print-config
./scripts/codex_mcp_launcher.py --register
./scripts/codex_mcp_launcher.py --run
```

