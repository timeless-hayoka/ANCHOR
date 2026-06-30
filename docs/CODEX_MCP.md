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

```json
{
  "mcpServers": {
    "anchor-codex": {
      "command": "python3",
      "args": ["codex_mcp_server.py"],
      "cwd": "/home/crexs/ANCHOR"
    }
  }
}
```

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

