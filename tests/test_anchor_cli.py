from __future__ import annotations

import importlib.util
import json
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


def test_parser_accepts_benchmark_compare():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "compare", "run-a", "run-b"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "compare"
    assert args.run_a == "run-a"
    assert args.run_b == "run-b"


def test_parser_accepts_benchmark_publish():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "publish", "run-a", "--note", "ship it"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "publish"
    assert args.run_id == "run-a"
    assert args.note == "ship it"


def test_parser_accepts_outcome_record():
    parser = anchor_cli.create_parser()
    args = parser.parse_args([
        "outcome", "record",
        "--stage", "accepted",
        "--target", "enzyme",
        "--run-id", "run-a",
        "--note", "validated",
    ])
    assert args.command == "outcome"
    assert args.outcome_command == "record"
    assert args.stage == "accepted"
    assert args.target == "enzyme"
    assert args.run_id == "run-a"
    assert args.note == "validated"


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
            "publication_tier": "published",
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


def test_render_benchmark_history_filters_development_by_default():
    rendered = anchor_cli.render_benchmark_history([
        {
            "id": "published-run",
            "level": "Phase 1",
            "confidence": "scaffold",
            "executed_at": "2026-06-27T00:23:21.000000+00:00",
            "publication_tier": "published",
            "results_summary": {"passed": 1, "failed": 0, "timed_out": 0, "detector_signals": 1, "medium_high_target_relevant_findings": 3},
        },
        {
            "id": "development-run",
            "level": "Phase 1",
            "confidence": "scaffold",
            "executed_at": "2026-06-27T00:24:21.000000+00:00",
            "publication_tier": "development",
            "results_summary": {"passed": 1, "failed": 0, "timed_out": 0, "detector_signals": 1, "medium_high_target_relevant_findings": 3},
        },
    ])
    assert "published-run" in rendered
    assert "development-run" not in rendered


def test_render_benchmark_history_can_include_development():
    rendered = anchor_cli.render_benchmark_history([
        {
            "id": "development-run",
            "level": "Phase 1",
            "confidence": "scaffold",
            "executed_at": "2026-06-27T00:24:21.000000+00:00",
            "publication_tier": "development",
            "results_summary": {"passed": 1, "failed": 0, "timed_out": 0, "detector_signals": 1, "medium_high_target_relevant_findings": 3},
        },
    ], include_development=True)
    assert "development-run" in rendered


def test_render_benchmark_compare_reports_deltas():
    rendered = anchor_cli.render_benchmark_compare(
        {
            "id": "run-a",
            "target": "damn-vulnerable-defi",
            "level": "Phase 1",
            "publication_tier": "development",
            "executed_at": "2026-06-27T00:10:52+00:00",
            "results_summary": {
                "passed": 1,
                "failed": 1,
                "timed_out": 1,
                "detector_signals": 3,
                "raw_detector_findings": 50,
                "target_relevant_detector_findings": 25,
                "medium_high_target_relevant_findings": 22,
            },
            "detector_provenance": {
                "slither": {"status": "available", "version": "0.11.5"},
                "mythril": {"status": "unavailable"},
            },
        },
        {
            "id": "run-b",
            "target": "damn-vulnerable-defi",
            "level": "Phase 1",
            "publication_tier": "published",
            "executed_at": "2026-06-27T00:23:21+00:00",
            "results_summary": {
                "passed": 2,
                "failed": 1,
                "timed_out": 0,
                "detector_signals": 4,
                "raw_detector_findings": 40,
                "target_relevant_detector_findings": 20,
                "medium_high_target_relevant_findings": 18,
            },
            "detector_provenance": {
                "slither": {"status": "available", "version": "0.11.5"},
                "mythril": {"status": "available"},
            },
        },
    )
    assert "Comparing `run-a` -> `run-b`" in rendered
    assert "passed: 1 -> 2 (delta +1)" in rendered
    assert "medium_high_target_relevant_findings: 22 -> 18 (delta -4)" in rendered


def test_cmd_benchmark_publish_updates_manifest_and_ledger(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "index.json"
    ledger_path = tmp_path / "ledger.jsonl"
    outcomes_dir = tmp_path / "outcomes"
    manifest_path.write_text(json.dumps({
        "history_policy": dict(anchor_cli.DEFAULT_HISTORY_POLICY),
        "benchmarks": [
            {"id": "run-a", "target": "damn-vulnerable-defi", "executed_at": "2026-06-27T00:23:21+00:00"}
        ],
    }))
    monkeypatch.setattr(anchor_cli, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(anchor_cli, "OUTCOMES_DIR", outcomes_dir)
    monkeypatch.setattr(anchor_cli, "OUTCOME_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(anchor_cli, "utcnow_iso", lambda: "2026-06-27T01:00:00+00:00")

    rc = anchor_cli.cmd_benchmark_publish(type("Args", (), {"run_id": "run-a", "note": "phase1 ready"}))
    assert rc == 0

    payload = json.loads(manifest_path.read_text())
    entry = payload["benchmarks"][0]
    assert entry["publication_tier"] == "published"
    assert entry["published_at"] == "2026-06-27T01:00:00+00:00"
    assert entry["publication_note"] == "phase1 ready"

    ledger_entries = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    assert ledger_entries[0]["stage"] == "benchmark_published"
    assert ledger_entries[0]["run_id"] == "run-a"

    out = capsys.readouterr().out
    assert "Published benchmark run: run-a" in out


def test_cmd_outcome_record_appends_ledger(tmp_path, monkeypatch, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    outcomes_dir = tmp_path / "outcomes"
    monkeypatch.setattr(anchor_cli, "OUTCOMES_DIR", outcomes_dir)
    monkeypatch.setattr(anchor_cli, "OUTCOME_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(anchor_cli, "utcnow_iso", lambda: "2026-06-27T02:00:00+00:00")

    rc = anchor_cli.cmd_outcome_record(type("Args", (), {
        "stage": "accepted",
        "target": "enzyme",
        "run_id": "run-a",
        "case_id": "case-1",
        "report_id": "immunefi-42",
        "note": "accepted for payout review",
    }))
    assert rc == 0

    ledger_entries = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    assert ledger_entries[0]["stage"] == "accepted"
    assert ledger_entries[0]["target"] == "enzyme"
    assert ledger_entries[0]["report_id"] == "immunefi-42"

    out = capsys.readouterr().out
    assert "Recorded outcome event: accepted" in out
