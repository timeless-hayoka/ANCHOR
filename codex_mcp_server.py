from __future__ import annotations

import subprocess
import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import anyio
import importlib
import mcp.types as types
from mcp.server.fastmcp import FastMCP
from mcp.shared.message import SessionMessage

fastmcp_server = importlib.import_module("mcp.server.fastmcp.server")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import anchor_cli
import anchor_work_queue



def _decode_stdio_line(line: str) -> SessionMessage | Exception | None:
    if not line.strip():
        return None
    try:
        message = types.JSONRPCMessage.model_validate_json(line)
    except Exception as exc:
        return exc
    return SessionMessage(message)


@asynccontextmanager
async def filtered_stdio_server(stdin: anyio.AsyncFile[str] | None = None, stdout: anyio.AsyncFile[str] | None = None):
    if not stdin:
        stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"))
    if not stdout:
        stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async def stdin_reader():
        try:
            async with read_stream_writer:
                async for line in stdin:
                    decoded = _decode_stdio_line(line)
                    if decoded is None:
                        continue
                    await read_stream_writer.send(decoded)
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async def stdout_writer():
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    payload = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                    await stdout.write(payload + "\n")
                    await stdout.flush()
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)
        yield read_stream, write_stream


app = FastMCP(
    "anchor-codex",
    instructions=(
        "Read-only MCP server for ANCHOR. Use it to inspect the work queue, "
        "benchmark snapshots, source-tool comparisons, and basic repo health."
    ),
)


def _git_status() -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--short", "--branch"],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "lines": [line for line in proc.stdout.splitlines() if line.strip()],
        "stderr": proc.stderr.strip(),
    }


def _top_level_entries(limit: int = 24) -> list[str]:
    names = []
    for path in sorted(ROOT.iterdir(), key=lambda p: p.name.lower()):
        if path.name.startswith('.'):
            continue
        if path.name in {"__pycache__", "node_modules", ".git"}:
            continue
        names.append(path.name)
    return names[:limit]


@app.tool(name="repo_status", description="Summarize the ANCHOR repository health and git state.")
def repo_status() -> dict[str, Any]:
    manifest = anchor_cli.load_manifest()
    latest = anchor_cli.find_latest_published_benchmark(manifest)
    return {
        "root": str(ROOT),
        "git": _git_status(),
        "top_level_entries": _top_level_entries(),
        "latest_published_benchmark": latest.get("id") if latest else None,
        "latest_published_target": latest.get("target") if latest else None,
    }


@app.tool(name="work_queue", description="Return the parsed ANCHOR work queue summary.")
def work_queue() -> dict[str, Any]:
    return anchor_work_queue.work_queue_summary()


@app.tool(name="benchmark_latest", description="Return the latest published benchmark snapshot and rendered summary.")
def benchmark_latest() -> dict[str, Any]:
    manifest = anchor_cli.load_manifest()
    entry = anchor_cli.find_latest_published_benchmark(manifest)
    if not entry:
        return {
            "status": "empty",
            "rendered": "No published benchmark available yet.",
        }
    compare = anchor_cli.load_source_tool_compare(entry)
    return {
        "status": "ok",
        "run_id": entry.get("id", "unknown"),
        "target": entry.get("target", "unknown"),
        "rendered": anchor_cli.render_benchmark_latest(entry),
        "source_tool_compare": compare,
    }


@app.tool(name="benchmark_compare_source", description="Return the source-tool comparison for a benchmark run.")
def benchmark_compare_source(run_id: str) -> dict[str, Any]:
    entries = anchor_cli.load_manifest()
    try:
        entry = anchor_cli.find_entry(entries, run_id)
    except KeyError:
        return {
            "status": "error",
            "message": f"Unknown run id: {run_id}",
        }

    compare = anchor_cli.load_source_tool_compare(entry)
    if not compare:
        return {
            "status": "empty",
            "run_id": run_id,
            "message": "No source-tool comparison data available for this run.",
        }
    return {
        "status": "ok",
        "run_id": run_id,
        "rendered": anchor_cli.render_benchmark_source_tool_compare(compare),
        "comparison": compare,
    }


@app.tool(name="benchmark_history", description="Return a rendered history table for recent benchmark runs.")
def benchmark_history(limit: int = 10) -> dict[str, Any]:
    entries = anchor_cli.load_manifest()
    rendered = anchor_cli.render_benchmark_history(entries[: max(0, limit)])
    return {
        "status": "ok",
        "limit": limit,
        "rendered": rendered,
    }


def main() -> None:
    fastmcp_server.stdio_server = filtered_stdio_server
    app.run("stdio")


if __name__ == "__main__":
    main()
