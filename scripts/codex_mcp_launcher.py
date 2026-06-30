#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "codex_mcp_server.py"


def registration_payload() -> dict[str, Any]:
    return {
        "mcpServers": {
            "anchor-codex": {
                "command": sys.executable,
                "args": [str(SERVER_PATH)],
                "cwd": str(ROOT),
            }
        }
    }


def print_registration() -> int:
    print(json.dumps(registration_payload(), indent=2))
    return 0


def register_with_codex() -> int:
    codex = shutil.which("codex")
    if not codex:
        print("codex CLI not found on PATH; use --print-config and register manually.", file=sys.stderr)
        return 1
    proc = subprocess.run(
        [codex, "mcp", "add", "anchor-codex", "--", sys.executable, str(SERVER_PATH)],
        cwd=ROOT,
        check=False,
    )
    return proc.returncode


def run_server() -> int:
    proc = subprocess.run([sys.executable, str(SERVER_PATH)], cwd=ROOT, check=False)
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex launcher for the ANCHOR MCP server")
    parser.add_argument("--print-config", action="store_true", help="Print the Codex MCP registration JSON")
    parser.add_argument("--register", action="store_true", help="Run codex mcp add for the local ANCHOR server")
    parser.add_argument("--run", action="store_true", help="Run the ANCHOR MCP server directly")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.print_config:
        return print_registration()
    if args.register:
        return register_with_codex()
    if args.run or not (args.print_config or args.register):
        return run_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
