#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "benchmarks" / "index.json"
BENCHMARK_RUNNERS = {
    ("dvd", "phase1"): ROOT / "benchmarks" / "damn-vulnerable-defi" / "run_phase1_benchmark.py",
}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anchor", description="ANCHOR local workflow entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    env_parser = sub.add_parser("env", help="Manage the local ANCHOR Python environment")
    env_sub = env_parser.add_subparsers(dest="env_command", required=True)
    env_init = env_sub.add_parser("init", help="Create a local .venv for ANCHOR")
    env_init.add_argument("--python", default=sys.executable, help="Python interpreter to use for the venv")

    benchmark_parser = sub.add_parser("benchmark", help="Run or inspect benchmark workflows")
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    benchmark_history = benchmark_sub.add_parser("history", help="Show published benchmark history")
    benchmark_history.add_argument("--limit", type=int, default=10, help="Maximum number of entries to show")

    target_parsers = {}
    for target in sorted({key[0] for key in BENCHMARK_RUNNERS}):
        target_parser = benchmark_sub.add_parser(target, help=f"Benchmark workflows for {target}")
        level_sub = target_parser.add_subparsers(dest="level", required=True)
        target_parsers[target] = level_sub

    for target, level in sorted(BENCHMARK_RUNNERS):
        target_parsers[target].add_parser(level, help=f"Run the {level} benchmark for {target}")

    return parser


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    payload = json.loads(MANIFEST_PATH.read_text())
    return payload.get("benchmarks", [])


def render_benchmark_history(entries: list[dict], limit: int = 10) -> str:
    rows = sorted(entries, key=lambda entry: entry.get("executed_at", ""), reverse=True)[:limit]
    if not rows:
        return "No benchmark history published yet."

    headers = ["RUN ID", "LEVEL", "PASS", "FAIL", "T/O", "SIG", "REL-HI", "CONF"]
    table = []
    for entry in rows:
        summary = entry.get("results_summary", {})
        table.append([
            entry.get("id", "unknown"),
            entry.get("level", "—"),
            str(summary.get("passed", "—")),
            str(summary.get("failed", "—")),
            str(summary.get("timed_out", "—")),
            str(summary.get("detector_signals", "—")),
            str(summary.get("medium_high_target_relevant_findings", "—")),
            entry.get("confidence", "—"),
        ])

    widths = [len(header) for header in headers]
    for row in table:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def fmt(row: list[str]) -> str:
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row))

    lines = [fmt(headers), fmt(["-" * width for width in widths])]
    lines.extend(fmt(row) for row in table)
    return "\n".join(lines)


def cmd_env_init(args: argparse.Namespace) -> int:
    venv_dir = ROOT / ".venv"
    subprocess.run([args.python, "-m", "venv", str(venv_dir)], check=True)
    pip_path = venv_dir / "bin" / "pip"
    requirements = ROOT / "requirements.txt"
    print(f"Created virtual environment at {venv_dir}")
    print(f"To finish setup, run: {pip_path} install -r {requirements}")
    return 0


def cmd_benchmark_history(args: argparse.Namespace) -> int:
    print(render_benchmark_history(load_manifest(), limit=args.limit))
    return 0


def cmd_benchmark_run(target: str, level: str) -> int:
    runner = BENCHMARK_RUNNERS[(target, level)]
    try:
        runpy.run_path(str(runner), run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "env" and args.env_command == "init":
        return cmd_env_init(args)
    if args.command == "benchmark" and args.benchmark_command == "history":
        return cmd_benchmark_history(args)
    if args.command == "benchmark":
        return cmd_benchmark_run(args.benchmark_command, args.level)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
