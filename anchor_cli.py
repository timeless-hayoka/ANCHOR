#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import runpy
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "benchmarks" / "index.json"
OUTCOMES_DIR = ROOT / "outcomes"
OUTCOME_LEDGER_PATH = OUTCOMES_DIR / "ledger.jsonl"
DEFAULT_HISTORY_POLICY = {
    "artifact_retention": "keep_all_successful_runs",
    "manifest_default_tier": "development",
    "default_history_view": "published_only",
    "published_tier": "published",
    "note": "Successful development reruns remain on disk, but only intentionally promoted runs are first-class published artifacts.",
}
OUTCOME_TYPES = ["benchmark", "pr", "issue", "finding"]
OUTCOME_STATUSES = ["open", "published", "triaged", "accepted", "rejected", "patched", "merged"]
LEGACY_STAGE_STATUS = {
    "benchmark_published": ("benchmark", "published"),
    "report_submitted": ("finding", "open"),
    "triaged": ("finding", "triaged"),
    "accepted": ("finding", "accepted"),
    "rejected": ("finding", "rejected"),
    "patched": ("finding", "patched"),
    "merged": ("pr", "merged"),
}
BENCHMARK_RUNNERS = {
    ("dvd", "phase1"): ROOT / "benchmarks" / "damn-vulnerable-defi" / "run_phase1_benchmark.py",
}


def utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anchor", description="ANCHOR local workflow entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    env_parser = sub.add_parser("env", help="Manage the local ANCHOR Python environment")
    env_sub = env_parser.add_subparsers(dest="env_command", required=True)
    env_init = env_sub.add_parser("init", help="Create a local .venv for ANCHOR")
    env_init.add_argument("--python", default=sys.executable, help="Python interpreter to use for the venv")

    benchmark_parser = sub.add_parser("benchmark", help="Run or inspect benchmark workflows")
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    benchmark_history = benchmark_sub.add_parser("history", help="Show benchmark history")
    benchmark_history.add_argument("--limit", type=int, default=10, help="Maximum number of entries to show")
    benchmark_history.add_argument("--all", action="store_true", help="Include development-tier reruns in addition to published artifacts")

    benchmark_compare = benchmark_sub.add_parser("compare", help="Compare two benchmark runs by manifest run id")
    benchmark_compare.add_argument("run_a")
    benchmark_compare.add_argument("run_b")

    benchmark_publish = benchmark_sub.add_parser("publish", help="Promote a run into first-class published benchmark history")
    benchmark_publish.add_argument("run_id")
    benchmark_publish.add_argument("--note", default="", help="Short publication note recorded in the manifest and outcome ledger")

    target_parsers = {}
    for target in sorted({key[0] for key in BENCHMARK_RUNNERS}):
        target_parser = benchmark_sub.add_parser(target, help=f"Benchmark workflows for {target}")
        level_sub = target_parser.add_subparsers(dest="level", required=True)
        target_parsers[target] = level_sub

    for target, level in sorted(BENCHMARK_RUNNERS):
        target_parsers[target].add_parser(level, help=f"Run the {level} benchmark for {target}")

    outcome_parser = sub.add_parser("outcome", help="Record and inspect real-world benchmark/report outcomes")
    outcome_sub = outcome_parser.add_subparsers(dest="outcome_command", required=True)

    outcome_history = outcome_sub.add_parser("history", help="Show recorded outcome ledger events")
    outcome_history.add_argument("--limit", type=int, default=10, help="Maximum number of outcome entries to show")

    outcome_summary = outcome_sub.add_parser("summary", help="Show aggregated outcome ledger status and lessons")
    outcome_summary.add_argument("--limit", type=int, default=5, help="Maximum number of recent lessons to show")

    outcome_add = outcome_sub.add_parser("add", help="Append a structured outcome event to the ledger")
    outcome_add.add_argument("--type", required=True, choices=OUTCOME_TYPES, help="Outcome object type")
    outcome_add.add_argument("--target", required=True, help="Benchmark family, protocol, repository, or target label")
    outcome_add.add_argument("--status", required=True, choices=OUTCOME_STATUSES, help="Outcome status")
    outcome_add.add_argument("--evidence", default="", help="Evidence pointer such as a run id, PR URL, issue URL, artifact path, or report link")
    outcome_add.add_argument("--lesson", default="", help="What ANCHOR learned from this outcome")
    outcome_add.add_argument("--run-id", default="", help="Benchmark run id if applicable")
    outcome_add.add_argument("--case-id", default="", help="Case id if applicable")
    outcome_add.add_argument("--report-id", default="", help="External report or submission id if applicable")
    outcome_add.add_argument("--note", default="", help="Short note for the outcome event")

    outcome_record = outcome_sub.add_parser("record", help=argparse.SUPPRESS)
    for action in outcome_add._actions:
        if action.dest in {"help"}:
            continue
        kwargs = {
            "dest": action.dest,
            "default": action.default,
            "required": getattr(action, "required", False),
            "help": argparse.SUPPRESS,
        }
        if action.option_strings:
            if getattr(action, "choices", None) is not None:
                kwargs["choices"] = action.choices
            if getattr(action, "const", None) is not None and action.nargs == 0:
                kwargs["const"] = action.const
            if getattr(action, "type", None) is not None:
                kwargs["type"] = action.type
            if getattr(action, "nargs", None) is not None:
                kwargs["nargs"] = action.nargs
            outcome_record.add_argument(*action.option_strings, **kwargs)

    return parser


def load_manifest_payload() -> dict:
    if not MANIFEST_PATH.exists():
        return {"history_policy": dict(DEFAULT_HISTORY_POLICY), "benchmarks": []}
    payload = json.loads(MANIFEST_PATH.read_text())
    payload.setdefault("history_policy", dict(DEFAULT_HISTORY_POLICY))
    payload.setdefault("benchmarks", [])
    return payload


def save_manifest_payload(payload: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def load_manifest() -> list[dict]:
    return load_manifest_payload().get("benchmarks", [])


def benchmark_tier(entry: dict) -> str:
    return entry.get("publication_tier", DEFAULT_HISTORY_POLICY["manifest_default_tier"])


def sorted_entries(entries: list[dict], reverse: bool = True) -> list[dict]:
    return sorted(entries, key=lambda entry: entry.get("executed_at", ""), reverse=reverse)


def find_entry(entries: list[dict], run_id: str) -> dict:
    for entry in entries:
        if entry.get("id") == run_id:
            return entry
    raise KeyError(run_id)


def metric_value(entry: dict, key: str) -> int | None:
    value = entry.get("results_summary", {}).get(key)
    return value if isinstance(value, int) else None


def format_delta(before: int | None, after: int | None) -> str:
    if before is None or after is None:
        return "n/a"
    delta = after - before
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def render_benchmark_history(entries: list[dict], limit: int = 10, include_development: bool = False) -> str:
    rows = sorted_entries(entries)
    if not include_development:
        rows = [entry for entry in rows if benchmark_tier(entry) == "published"]
    rows = rows[:limit]
    if not rows:
        scope = "published benchmark history" if not include_development else "benchmark history"
        return f"No {scope} available yet."

    headers = ["RUN ID", "TIER", "LEVEL", "PASS", "FAIL", "T/O", "SIG", "REL-HI", "CONF"]
    table = []
    for entry in rows:
        summary = entry.get("results_summary", {})
        table.append([
            entry.get("id", "unknown"),
            benchmark_tier(entry),
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


def render_benchmark_compare(entry_a: dict, entry_b: dict) -> str:
    lines = [
        f"Comparing `{entry_a.get('id')}` -> `{entry_b.get('id')}`",
        "",
        "Metadata",
        f"- target: {entry_a.get('target', 'unknown')} -> {entry_b.get('target', 'unknown')}",
        f"- level: {entry_a.get('level', 'unknown')} -> {entry_b.get('level', 'unknown')}",
        f"- tier: {benchmark_tier(entry_a)} -> {benchmark_tier(entry_b)}",
        f"- executed_at: {entry_a.get('executed_at', 'unknown')} -> {entry_b.get('executed_at', 'unknown')}",
        "",
        "Summary deltas",
    ]
    for key, label in [
        ("passed", "passed"),
        ("failed", "failed"),
        ("timed_out", "timed_out"),
        ("detector_signals", "detector_signals"),
        ("raw_detector_findings", "raw_detector_findings"),
        ("target_relevant_detector_findings", "target_relevant_detector_findings"),
        ("medium_high_target_relevant_findings", "medium_high_target_relevant_findings"),
    ]:
        before = metric_value(entry_a, key)
        after = metric_value(entry_b, key)
        lines.append(f"- {label}: {before if before is not None else '—'} -> {after if after is not None else '—'} (delta {format_delta(before, after)})")

    prov_a = entry_a.get("detector_provenance", {})
    prov_b = entry_b.get("detector_provenance", {})
    slither_a = prov_a.get("slither", {})
    slither_b = prov_b.get("slither", {})
    myth_a = prov_a.get("mythril", {})
    myth_b = prov_b.get("mythril", {})
    lines.extend([
        "",
        "Detector provenance",
        f"- slither: {slither_a.get('status', '—')} {slither_a.get('version', '')} -> {slither_b.get('status', '—')} {slither_b.get('version', '')}",
        f"- mythril: {myth_a.get('status', '—')} -> {myth_b.get('status', '—')}",
    ])
    return "\n".join(lines)


def ensure_outcome_dir() -> None:
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)


def infer_outcome_type(entry: dict) -> str:
    if entry.get("type") in OUTCOME_TYPES:
        return entry["type"]
    stage = entry.get("stage", "")
    if stage in LEGACY_STAGE_STATUS:
        return LEGACY_STAGE_STATUS[stage][0]
    return "finding"


def infer_outcome_status(entry: dict) -> str:
    if entry.get("status") in OUTCOME_STATUSES:
        return entry["status"]
    stage = entry.get("stage", "")
    if stage in LEGACY_STAGE_STATUS:
        return LEGACY_STAGE_STATUS[stage][1]
    return "open"


def normalize_outcome_entry(entry: dict) -> dict:
    normalized = dict(entry)
    normalized.setdefault("timestamp", "unknown")
    normalized["type"] = infer_outcome_type(entry)
    normalized["status"] = infer_outcome_status(entry)
    normalized.setdefault("target", "")
    normalized.setdefault("run_id", "")
    normalized.setdefault("case_id", "")
    normalized.setdefault("report_id", "")
    normalized.setdefault("note", "")
    normalized.setdefault("lesson", "")
    normalized.setdefault("evidence", "")
    if not normalized["evidence"]:
        normalized["evidence"] = normalized.get("report_id") or normalized.get("run_id") or normalized.get("note", "")
    return normalized


def load_outcome_entries() -> list[dict]:
    if not OUTCOME_LEDGER_PATH.exists():
        return []
    entries = []
    for line in OUTCOME_LEDGER_PATH.read_text().splitlines():
        if not line.strip():
            continue
        entries.append(normalize_outcome_entry(json.loads(line)))
    return entries


def append_outcome_entry(entry: dict) -> None:
    ensure_outcome_dir()
    with OUTCOME_LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def summarize_text(value: str, limit: int = 36) -> str:
    text = str(value or "—")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def render_outcome_history(entries: list[dict], limit: int = 10) -> str:
    rows = sorted(entries, key=lambda entry: entry.get("timestamp", ""), reverse=True)[:limit]
    if not rows:
        return "No outcome ledger entries recorded yet."

    headers = ["TIMESTAMP", "TYPE", "STATUS", "TARGET", "RUN ID", "REPORT", "LESSON"]
    table = []
    for entry in rows:
        table.append([
            entry.get("timestamp", "unknown"),
            entry.get("type", "unknown"),
            entry.get("status", "unknown"),
            entry.get("target", "—") or "—",
            entry.get("run_id", "—") or "—",
            entry.get("report_id", "—") or "—",
            summarize_text(entry.get("lesson", "") or entry.get("note", "—"), limit=42),
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


def render_outcome_summary(entries: list[dict], lesson_limit: int = 5) -> str:
    if not entries:
        return "No outcome ledger entries recorded yet."

    normalized = sorted(entries, key=lambda entry: entry.get("timestamp", ""), reverse=True)
    by_type = Counter(entry.get("type", "unknown") for entry in normalized)
    by_status = Counter(entry.get("status", "unknown") for entry in normalized)
    by_target = Counter(entry.get("target", "") or "unlabeled" for entry in normalized)

    lines = [
        "Outcome summary",
        f"- total events: {len(normalized)}",
        f"- status mix: " + ", ".join(f"{status}={by_status[status]}" for status in OUTCOME_STATUSES if by_status.get(status)),
        f"- type mix: " + ", ".join(f"{kind}={by_type[kind]}" for kind in OUTCOME_TYPES if by_type.get(kind)),
        "",
        "Top targets",
    ]
    for target, count in by_target.most_common(5):
        lines.append(f"- {target}: {count} event(s)")

    lessons = [entry for entry in normalized if entry.get("lesson")]
    lines.extend(["", "Recent lessons"])
    if not lessons:
        lines.append("- No lessons recorded yet.")
    else:
        for entry in lessons[:lesson_limit]:
            lines.append(f"- {entry.get('timestamp', 'unknown')} · {entry.get('target', 'unlabeled')}: {entry.get('lesson')}")

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
    print(render_benchmark_history(load_manifest(), limit=args.limit, include_development=args.all))
    return 0


def cmd_benchmark_compare(args: argparse.Namespace) -> int:
    entries = load_manifest()
    try:
        entry_a = find_entry(entries, args.run_a)
        entry_b = find_entry(entries, args.run_b)
    except KeyError as exc:
        print(f"Unknown run id: {exc.args[0]}", file=sys.stderr)
        return 1
    print(render_benchmark_compare(entry_a, entry_b))
    return 0


def cmd_benchmark_publish(args: argparse.Namespace) -> int:
    payload = load_manifest_payload()
    entries = payload.get("benchmarks", [])
    try:
        entry = find_entry(entries, args.run_id)
    except KeyError:
        print(f"Unknown run id: {args.run_id}", file=sys.stderr)
        return 1
    entry["publication_tier"] = "published"
    entry["published_at"] = utcnow_iso()
    if args.note:
        entry["publication_note"] = args.note
    save_manifest_payload(payload)
    append_outcome_entry({
        "timestamp": utcnow_iso(),
        "type": "benchmark",
        "status": "published",
        "stage": "benchmark_published",
        "target": entry.get("target", ""),
        "run_id": entry.get("id", ""),
        "case_id": "",
        "report_id": "",
        "evidence": entry.get("record", "") or entry.get("artifact_json", ""),
        "lesson": "",
        "note": args.note or "Published benchmark artifact",
    })
    print(f"Published benchmark run: {entry.get('id')}")
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


def cmd_outcome_history(args: argparse.Namespace) -> int:
    print(render_outcome_history(load_outcome_entries(), limit=args.limit))
    return 0


def cmd_outcome_summary(args: argparse.Namespace) -> int:
    print(render_outcome_summary(load_outcome_entries(), lesson_limit=args.limit))
    return 0


def cmd_outcome_add(args: argparse.Namespace) -> int:
    entry = {
        "timestamp": utcnow_iso(),
        "type": args.type,
        "status": args.status,
        "target": args.target,
        "run_id": args.run_id,
        "case_id": args.case_id,
        "report_id": args.report_id,
        "evidence": args.evidence,
        "lesson": args.lesson,
        "note": args.note,
    }
    append_outcome_entry(entry)
    print(f"Recorded outcome event: {args.type} {args.status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "env" and args.env_command == "init":
        return cmd_env_init(args)
    if args.command == "benchmark" and args.benchmark_command == "history":
        return cmd_benchmark_history(args)
    if args.command == "benchmark" and args.benchmark_command == "compare":
        return cmd_benchmark_compare(args)
    if args.command == "benchmark" and args.benchmark_command == "publish":
        return cmd_benchmark_publish(args)
    if args.command == "benchmark":
        return cmd_benchmark_run(args.benchmark_command, args.level)
    if args.command == "outcome" and args.outcome_command == "history":
        return cmd_outcome_history(args)
    if args.command == "outcome" and args.outcome_command == "summary":
        return cmd_outcome_summary(args)
    if args.command == "outcome" and args.outcome_command in {"add", "record"}:
        return cmd_outcome_add(args)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
