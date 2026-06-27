from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("anchor_cli", ROOT / "anchor_cli.py")
anchor_cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(anchor_cli)


def test_parser_accepts_benchmark_phase1():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "dvd", "phase1"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "dvd"
    assert args.level == "phase1"


def test_parser_accepts_benchmark_history():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "history", "--limit", "5"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "history"
    assert args.limit == 5


def test_parser_accepts_env_init_python_override():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["env", "init", "--python", "/usr/bin/python3"])
    assert args.command == "env"
    assert args.env_command == "init"
    assert args.python == "/usr/bin/python3"


def test_render_benchmark_history_contains_scoped_columns():
    rendered = anchor_cli.render_benchmark_history([
        {
            "id": "dvd-phase1-local-2026-06-26T23-47-11Z",
            "level": "Phase 1",
            "confidence": "scaffold",
            "executed_at": "2026-06-26T23:47:11.000000+00:00",
            "results_summary": {
                "passed": 1,
                "failed": 1,
                "timed_out": 1,
                "detector_signals": 3,
                "medium_high_target_relevant_findings": 22,
            },
        }
    ])
    assert "RUN ID" in rendered
    assert "REL-HI" in rendered
    assert "dvd-phase1-local-2026-06-26T23-47-11Z" in rendered
    assert "22" in rendered
