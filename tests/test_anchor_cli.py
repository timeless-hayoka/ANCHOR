from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


anchor_cli = load_module("anchor_cli", "anchor_cli.py")
anchor_scripts = load_module("anchor_scripts", "anchor_scripts.py")
hunt_planner = load_module("hunt_planner", "hunt_planner.py")
anchor_storage = load_module("anchor_storage", "anchor_storage.py")
anchor_work_queue = load_module("anchor_work_queue", "anchor_work_queue.py")
scabench_adapter = load_module("scabench_adapter", "scabench_adapter.py")
github_discovery = load_module("github_discovery", "github_discovery.py")


def test_parser_accepts_benchmark_phase1():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "dvd", "phase1"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "dvd"
    assert args.level == "phase1"


def test_parser_accepts_ethernaut_phase1():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "ethernaut", "phase1"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "ethernaut"
    assert args.level == "phase1"


def test_parser_accepts_ethernaut_source_comparison():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "ethernaut", "source-comparison"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "ethernaut"
    assert args.level == "source-comparison"


def test_parser_accepts_sarif_known_findings():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "sarif", "known-findings"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "sarif"
    assert args.level == "known-findings"


def test_parser_accepts_defihacklabs_source_comparison():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "defihacklabs", "source-comparison"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "defihacklabs"
    assert args.level == "source-comparison"


def test_parser_accepts_benchmark_compare_source():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "compare-source", "run-a", "--json"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "compare-source"
    assert args.run_id == "run-a"
    assert args.json is True


def test_parser_accepts_codex_mcp():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["codex", "mcp", "--print-config"])
    assert args.command == "codex"
    assert args.codex_command == "mcp"
    assert args.print_config is True


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



def test_parser_accepts_benchmark_latest():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "latest"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "latest"


def test_parser_accepts_benchmark_trends():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "trends", "--limit", "5", "--json"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "trends"
    assert args.limit == 5
    assert args.json is True


def test_parser_accepts_strategy():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["strategy", "--limit", "5", "--json"])
    assert args.command == "strategy"
    assert args.limit == 5
    assert args.json is True


def test_parser_accepts_work_queue():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["work", "queue", "--json"])
    assert args.command == "work"
    assert args.work_command == "queue"
    assert args.json is True


def test_parser_accepts_hunt_plan():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["hunt", "plan", "--target", "targets/enzyme-blue.md", "--json"])
    assert args.command == "hunt"
    assert args.hunt_command == "plan"
    assert args.target == "targets/enzyme-blue.md"
    assert args.json is True


def test_parser_accepts_github_crawl():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["github", "crawl", "--query", "solidity fuzzing", "--limit", "8", "--no-readmes"])
    assert args.command == "github"
    assert args.github_command == "crawl"
    assert args.query == ["solidity fuzzing"]
    assert args.limit == 8
    assert args.no_readmes is True


def test_parser_accepts_github_profile_crawls():
    parser = anchor_cli.create_parser()
    cases = [
        (["github", "crawl-auth", "--limit", "7"], "crawl-auth"),
        (["github", "crawl-upgrade", "--limit", "7"], "crawl-upgrade"),
        (["github", "crawl-accounting", "--limit", "7"], "crawl-accounting"),
        (["github", "crawl-oracle", "--limit", "7"], "crawl-oracle"),
        (["github", "crawl-external", "--limit", "7"], "crawl-external"),
    ]
    for argv, command in cases:
        args = parser.parse_args(argv)
        assert args.command == "github"
        assert args.github_command == command
        assert args.limit == 7


def test_parser_accepts_github_select():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["github", "select", "perimetersec/fuzzlib"])
    assert args.command == "github"
    assert args.github_command == "select"
    assert args.repo == "perimetersec/fuzzlib"


def test_parser_accepts_github_plan():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["github", "plan", "perimetersec/fuzzlib", "--run-id", "2026-06-29", "--json"])
    assert args.command == "github"
    assert args.github_command == "plan"
    assert args.repo == "perimetersec/fuzzlib"
    assert args.run_id == "2026-06-29"
    assert args.json is True


def test_parser_accepts_github_scope_check():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["github", "scope-check", "perimetersec/fuzzlib", "--json"])
    assert args.command == "github"
    assert args.github_command == "scope-check"
    assert args.repo == "perimetersec/fuzzlib"
    assert args.json is True


def test_parser_accepts_benchmark_publish():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["benchmark", "publish", "run-a", "--note", "ship it"])
    assert args.command == "benchmark"
    assert args.benchmark_command == "publish"
    assert args.run_id == "run-a"
    assert args.note == "ship it"


def test_parser_accepts_outcome_add_with_links():
    parser = anchor_cli.create_parser()
    args = parser.parse_args([
        "outcome", "add",
        "--id", "entry-1",
        "--type", "finding",
        "--target", "enzyme",
        "--status", "accepted",
        "--evidence", "benchmarks/dvd/README.md",
        "--lesson", "proof gate held",
        "--run-id", "run-a",
        "--benchmark-id", "bench-a",
        "--claim-id", "claim-a",
        "--link-benchmark", "benchmarks/index.json",
        "--link-artifact", "artifacts/evidence.json",
        "--link-report", "https://immunefi.com/report/1",
    ])
    assert args.command == "outcome"
    assert args.outcome_command == "add"
    assert args.type == "finding"
    assert args.status == "accepted"
    assert args.id == "entry-1"
    assert args.benchmark_id == "bench-a"
    assert args.claim_id == "claim-a"
    assert args.link_report == "https://immunefi.com/report/1"


def test_parser_accepts_outcome_summary():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["outcome", "summary", "--limit", "3"])
    assert args.command == "outcome"
    assert args.outcome_command == "summary"
    assert args.limit == 3


def test_parser_accepts_outcome_insights():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["outcome", "insights", "--limit", "50", "--top", "4"])
    assert args.command == "outcome"
    assert args.outcome_command == "insights"
    assert args.limit == 50
    assert args.top == 4


def test_parser_accepts_legacy_outcome_record_alias():
    parser = anchor_cli.create_parser()
    args = parser.parse_args([
        "outcome", "record",
        "--type", "issue",
        "--target", "solmate",
        "--status", "open",
    ])
    assert args.command == "outcome"
    assert args.outcome_command == "record"
    assert args.type == "issue"
    assert args.status == "open"


def test_parser_accepts_env_init_python_override():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["env", "init", "--python", "/usr/bin/python3"])
    assert args.command == "env"
    assert args.env_command == "init"
    assert args.python == "/usr/bin/python3"


def test_parser_accepts_sarif_process_when_available():
    if not anchor_cli.HAS_SARIF:
        return
    parser = anchor_cli.create_parser()
    args = parser.parse_args([
        "sarif", "process",
        "slither.sarif", "codeql.sarif",
        "--db", "my_findings.db",
        "--llm",
    ])
    assert args.command == "sarif"
    assert args.sarif_command == "process"
    assert args.sarif_files == ["slither.sarif", "codeql.sarif"]
    assert args.db == "my_findings.db"
    assert args.llm is True


def test_parser_accepts_sarif_visualize_when_available():
    if not anchor_cli.HAS_SARIF:
        return
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["sarif", "visualize", "--output", "clusters.html"])
    assert args.command == "sarif"
    assert args.sarif_command == "visualize"
    assert args.output == "clusters.html"


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
        {
            "id": "published-run",
            "level": "Phase 1",
            "confidence": "scaffold",
            "executed_at": "2026-06-26T23:24:21.000000+00:00",
            "publication_tier": "published",
            "results_summary": {"passed": 2, "failed": 0, "timed_out": 0, "detector_signals": 2, "medium_high_target_relevant_findings": 5},
        },
    ], include_development=True)
    assert rendered.index("published-run") < rendered.index("development-run")


def test_render_benchmark_compare_reports_deltas(monkeypatch):
    def fake_metrics(entry):
        if entry["id"] == "run-a":
            return {
                "schema_version": "1.0",
                "benchmark": "sarif-known-findings",
                "run_id": "run-a",
                "source_commit": "aaa111",
                "counts": {
                    "true_positive": 3,
                    "false_positive": 1,
                    "false_negative": 0,
                    "true_negative": 0,
                    "duplicates_removed": 1,
                },
                "metrics": {"precision": 0.75, "recall": 1.0, "f1": 0.8571},
                "runtime_seconds": 10,
                "tool_versions": {},
            }
        return {
            "schema_version": "1.0",
            "benchmark": "sarif-known-findings",
            "run_id": "run-b",
            "source_commit": "bbb222",
            "counts": {
                "true_positive": 4,
                "false_positive": 1,
                "false_negative": 0,
                "true_negative": 0,
                "duplicates_removed": 1,
            },
            "metrics": {"precision": 0.8, "recall": 0.9, "f1": 0.8421},
            "runtime_seconds": 12,
            "tool_versions": {},
        }
    monkeypatch.setattr(anchor_cli, "load_benchmark_metrics", fake_metrics)
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
    assert "Guardrail: FAIL" in rendered
    assert "precision: 0.75 -> 0.8 (delta +0.05)" in rendered
    assert "recall: 1.0 -> 0.9 (delta -0.1)" in rendered
    assert "f1: 0.8571 -> 0.8421 (delta -0.015)" in rendered
    assert "true_positive: +1" in rendered
    assert "false_negative: +0" in rendered
    assert "runtime_seconds: 10 -> 12 (delta +2)" in rendered




def test_cmd_benchmark_compare_source_reports_source_delta(monkeypatch, capsys):
    entries = [
        {"id": "run-a", "target": "defihacklabs", "level": "Phase 3", "executed_at": "2026-06-29T18:46:05+00:00"},
    ]
    compare = {
        "schema_version": "1.0",
        "benchmark": "defihacklabs-source-comparison",
        "run_id": "run-a",
        "source_tool": "slither",
        "comparison": {
            "anchor_visible": 4,
            "source_tool_visible": 4,
            "shared_visible": 3,
            "anchor_only": 1,
            "source_only": 1,
            "shared_hidden": 0,
            "agreement": 3,
            "visible_delta": 0,
        },
        "cases": [
            {"id": "fallback-owner-check", "anchor_visible": True, "source_tool_visible": True, "comparison": "shared_visible", "anchor_classification": "TP"},
        ],
    }
    monkeypatch.setattr(anchor_cli, "load_manifest", lambda: entries)
    monkeypatch.setattr(anchor_cli, "find_entry", lambda entries_arg, run_id: next(item for item in entries_arg if item["id"] == run_id))
    monkeypatch.setattr(anchor_cli, "load_source_tool_compare", lambda entry: compare)
    rc = anchor_cli.cmd_benchmark_compare_source(type("Args", (), {"run_id": "run-a", "json": False}))
    captured = capsys.readouterr()
    assert rc == 0
    assert "Source Tool Comparison" in captured.out
    assert "source_tool: slither" in captured.out
    assert "anchor_only: 1" in captured.out
    assert "source_only: 1" in captured.out

def test_cmd_benchmark_compare_fails_on_recall_drop(monkeypatch, capsys):
    entries = [
        {"id": "run-a", "target": "demo", "level": "Phase 1", "executed_at": "2026-06-27T00:10:52+00:00"},
        {"id": "run-b", "target": "demo", "level": "Phase 1", "executed_at": "2026-06-27T00:23:21+00:00"},
    ]
    monkeypatch.setattr(anchor_cli, "load_manifest", lambda: entries)
    monkeypatch.setattr(anchor_cli, "find_entry", lambda entries_arg, run_id: next(item for item in entries_arg if item["id"] == run_id))
    monkeypatch.setattr(anchor_cli, "benchmark_compare_metrics", lambda a, b: {"status": "FAIL" if b["id"] == "run-b" else "PASS"})
    monkeypatch.setattr(anchor_cli, "render_benchmark_compare", lambda a, b: "comparison output")

    rc = anchor_cli.cmd_benchmark_compare(type("Args", (), {"run_a": "run-a", "run_b": "run-b"}))
    captured = capsys.readouterr()
    assert rc == 1
    assert "comparison output" in captured.out


def test_github_discovery_summary_renders_clean_table(tmp_path):
    bundle = {
        "generated_at": "2026-06-29T00:00:00+00:00",
        "queries": ["solidity fuzzing"],
        "summary": {"selected": 1, "join": 1, "watch": 0, "skip": 0},
        "candidates": [
            {
                "full_name": "crytic/echidna",
                "score": 11,
                "recommendation": "join",
                "stars": 3400,
                "open_issues": 63,
                "language": "Haskell",
                "topics": ["solidity", "fuzzing", "invariants"],
                "readme_excerpt": "Echidna is a smart-contract fuzzer.",
                "reasons": ["README present", "recently updated"],
                "signals": [{"name": "docs", "value": "README present", "weight": 2}],
                "issue_angles": ["testing/invariants", "docs/workflow clarity", "regression harness or machine-readable output"],
            }
        ],
    }
    run_dir = tmp_path / "bundle"
    run_dir.mkdir()
    rendered = github_discovery.render_summary(bundle, run_dir=run_dir)
    assert "GitHub Discovery Bundle" in rendered
    assert "crytic/echidna" in rendered
    assert "join" in rendered
    assert "bundle.json" in rendered



def test_find_latest_published_benchmark_prefers_newest_published_run():
    latest = anchor_cli.find_latest_published_benchmark([
        {
            "id": "old-published",
            "executed_at": "2026-06-26T23:24:21.000000+00:00",
            "publication_tier": "published",
        },
        {
            "id": "new-published",
            "executed_at": "2026-06-27T23:24:21.000000+00:00",
            "publication_tier": "published",
        },
        {
            "id": "development-run",
            "executed_at": "2026-06-28T23:24:21.000000+00:00",
            "publication_tier": "development",
        },
    ])
    assert latest["id"] == "new-published"


def test_render_benchmark_latest_includes_regression_and_artifacts():
    current = {
        "id": "new-published",
        "target": "damn-vulnerable-defi",
        "level": "Phase 1",
        "confidence": "high",
        "executed_at": "2026-06-27T23:24:21.000000+00:00",
        "publication_tier": "published",
        "results_summary": {"passed": 16, "failed": 2, "timed_out": 0, "detector_signals": 18, "medium_high_target_relevant_findings": 58},
        "regression_report": "benchmarks/damn-vulnerable-defi/runs/new-published/REGRESSION_REPORT.md",
        "published_record": "benchmarks/damn-vulnerable-defi/runs/new-published/PUBLISHED.md",
        "storage_manifest": "benchmarks/damn-vulnerable-defi/runs/new-published/storage.json",
        "artifact_json": "benchmarks/damn-vulnerable-defi/runs/new-published/benchmark.json",
        "source_tool_compare_json": "benchmarks/damn-vulnerable-defi/runs/new-published/source_tool_compare.json",
    }
    baseline = {
        "id": "old-published",
        "target": "damn-vulnerable-defi",
        "level": "Phase 1",
        "confidence": "scaffold",
        "executed_at": "2026-06-26T23:24:21.000000+00:00",
        "publication_tier": "published",
        "results_summary": {"passed": 15, "failed": 2, "timed_out": 1, "detector_signals": 17, "medium_high_target_relevant_findings": 56},
    }
    original_load = anchor_cli.load_benchmark_artifact
    def fake_load_benchmark_artifact(entry):
        if entry and entry.get("id") == "new-published":
            return {
                "summary": current["results_summary"],
                "results": [
                    {"challenge": "wallet-mining", "status": "PASSED"},
                    {"challenge": "curvy-puppet", "status": "FAILED"},
                    {"challenge": "puppet-v3", "status": "FAILED"},
                ],
            }
        if entry and entry.get("id") == "old-published":
            return {
                "summary": baseline["results_summary"],
                "results": [
                    {"challenge": "wallet-mining", "status": "TIMED_OUT"},
                    {"challenge": "curvy-puppet", "status": "FAILED"},
                    {"challenge": "puppet-v3", "status": "FAILED"},
                ],
            }
        return {"summary": {}, "results": []}
    anchor_cli.load_benchmark_artifact = fake_load_benchmark_artifact
    try:
        rendered = anchor_cli.render_benchmark_latest(current, baseline)
    finally:
        anchor_cli.load_benchmark_artifact = original_load
    assert "Latest Published Benchmark" in rendered
    assert "Run: new-published" in rendered
    assert "Confidence: high" in rendered
    assert "- resolved: 1" in rendered
    assert "- regressions: 0" in rendered
    assert "- environment_sensitive: 0" in rendered
    assert "Source Tool Comparison" in rendered
    assert "anchor_only" in rendered
    assert "benchmarks/damn-vulnerable-defi/runs/new-published/REGRESSION_REPORT.md" in rendered
    assert "benchmarks/damn-vulnerable-defi/runs/new-published/PUBLISHED.md" in rendered


def test_render_benchmark_latest_includes_source_tool_comparison_summary():
    current = {
        "id": "new-source-comparison",
        "target": "defihacklabs",
        "level": "Phase 3",
        "confidence": "measured",
        "executed_at": "2026-06-29T18:46:05.000000+00:00",
        "publication_tier": "published",
        "results_summary": {"passed": 4, "failed": 1, "timed_out": 0, "detector_signals": 4, "medium_high_target_relevant_findings": 1},
        "regression_report": "benchmarks/defihacklabs/source-comparison/runs/new-source-comparison/REGRESSION_REPORT.md",
        "published_record": "benchmarks/defihacklabs/source-comparison/runs/new-source-comparison/PUBLISHED.md",
        "storage_manifest": "benchmarks/defihacklabs/source-comparison/runs/new-source-comparison/storage.json",
        "artifact_json": "benchmarks/defihacklabs/source-comparison/runs/new-source-comparison/benchmark.json",
        "source_tool_compare_json": "benchmarks/defihacklabs/source-comparison/runs/new-source-comparison/source_tool_compare.json",
    }
    compare = {
        "schema_version": "1.0",
        "benchmark": "defihacklabs-source-comparison",
        "run_id": "defihacklabs-source-comparison-new-source-comparison",
        "source_tool": "slither",
        "comparison": {
            "anchor_visible": 4,
            "source_tool_visible": 4,
            "shared_visible": 3,
            "anchor_only": 1,
            "source_only": 1,
            "shared_hidden": 0,
            "agreement": 3,
            "visible_delta": 0,
        },
        "cases": [
            {"id": "fallback-owner-check", "anchor_visible": True, "source_tool_visible": True, "comparison": "shared_visible", "anchor_classification": "TP"},
        ],
    }
    original_load_artifact = anchor_cli.load_benchmark_artifact
    original_load_compare = anchor_cli.load_source_tool_compare
    original_load_manifest = anchor_cli.load_manifest
    original_load_outcomes = anchor_cli.load_outcome_entries
    def fake_load_benchmark_artifact(entry):
        if entry and entry.get("id") == current["id"]:
            return {"summary": current["results_summary"], "results": []}
        return {"summary": {}, "results": []}
    anchor_cli.load_benchmark_artifact = fake_load_benchmark_artifact
    anchor_cli.load_source_tool_compare = lambda entry: compare if entry and entry.get("id") == current["id"] else {}
    anchor_cli.load_manifest = lambda: [current]
    anchor_cli.load_outcome_entries = lambda: []
    try:
        rendered = anchor_cli.render_benchmark_latest(current, None)
    finally:
        anchor_cli.load_benchmark_artifact = original_load_artifact
        anchor_cli.load_source_tool_compare = original_load_compare
        anchor_cli.load_manifest = original_load_manifest
        anchor_cli.load_outcome_entries = original_load_outcomes
    assert "Source Tool Comparison" in rendered
    assert "source_tool: slither" in rendered
    assert "anchor_visible: 4" in rendered
    assert "source_only: 1" in rendered
    assert "compare_report: benchmarks/defihacklabs/source-comparison/runs/new-source-comparison/source_tool_compare.json" in rendered

def test_render_benchmark_latest_includes_research_loop_summary():
    current = {
        "id": "new-published",
        "target": "damn-vulnerable-defi",
        "level": "Phase 1",
        "confidence": "high",
        "executed_at": "2026-06-27T23:24:21.000000+00:00",
        "publication_tier": "published",
        "results_summary": {"passed": 16, "failed": 2, "timed_out": 0, "detector_signals": 18, "medium_high_target_relevant_findings": 58},
        "regression_report": "benchmarks/damn-vulnerable-defi/runs/new-published/REGRESSION_REPORT.md",
        "published_record": "benchmarks/damn-vulnerable-defi/runs/new-published/PUBLISHED.md",
        "storage_manifest": "benchmarks/damn-vulnerable-defi/runs/new-published/storage.json",
        "artifact_json": "benchmarks/damn-vulnerable-defi/runs/new-published/benchmark.json",
    }
    baseline = {
        "id": "old-published",
        "target": "damn-vulnerable-defi",
        "level": "Phase 1",
        "confidence": "scaffold",
        "executed_at": "2026-06-26T23:24:21.000000+00:00",
        "publication_tier": "published",
        "results_summary": {"passed": 15, "failed": 2, "timed_out": 1, "detector_signals": 17, "medium_high_target_relevant_findings": 56},
    }
    original_load_artifact = anchor_cli.load_benchmark_artifact
    original_load_manifest = anchor_cli.load_manifest
    original_load_outcomes = anchor_cli.load_outcome_entries
    def fake_load_benchmark_artifact(entry):
        if entry and entry.get("id") == "new-published":
            return {
                "summary": current["results_summary"],
                "results": [
                    {"challenge": "wallet-mining", "status": "PASSED"},
                    {"challenge": "curvy-puppet", "status": "FAILED"},
                    {"challenge": "puppet-v3", "status": "FAILED"},
                ],
            }
        if entry and entry.get("id") == "old-published":
            return {
                "summary": baseline["results_summary"],
                "results": [
                    {"challenge": "wallet-mining", "status": "TIMED_OUT"},
                    {"challenge": "curvy-puppet", "status": "FAILED"},
                    {"challenge": "puppet-v3", "status": "FAILED"},
                ],
            }
        return {"summary": {}, "results": []}
    anchor_cli.load_benchmark_artifact = fake_load_benchmark_artifact
    anchor_cli.load_manifest = lambda: [baseline, current]
    anchor_cli.load_outcome_entries = lambda: [{"timestamp": "2026-06-27T00:00:00+00:00", "type": "benchmark", "status": "published", "target": "damn-vulnerable-defi", "lesson": "wallet-mining timed out"}]
    try:
        rendered = anchor_cli.render_benchmark_latest(current, baseline)
    finally:
        anchor_cli.load_benchmark_artifact = original_load_artifact
        anchor_cli.load_manifest = original_load_manifest
        anchor_cli.load_outcome_entries = original_load_outcomes
    assert "Research Loop" in rendered
    assert "- queue_depth:" in rendered
    assert "- assumptions:" in rendered
    assert "- universes:" in rendered
    assert "- incentive_surface:" in rendered
    assert "- mev_models:" in rendered


def test_normalize_outcome_entry_supports_legacy_and_links():
    normalized = anchor_cli.normalize_outcome_entry({
        "timestamp": "2026-06-27T01:00:00+00:00",
        "stage": "benchmark_published",
        "target": "damn-vulnerable-defi",
        "run_id": "dvd-run",
        "link_artifact": "benchmarks/run-a.json",
        "note": "published scaffold",
    })
    assert normalized["type"] == "benchmark"
    assert normalized["status"] == "published"
    assert normalized["links"]["artifact"] == "benchmarks/run-a.json"
    assert normalized["benchmark_id"] == "dvd-run"


def test_render_outcome_history_supports_structured_and_legacy_entries():
    rendered = anchor_cli.render_outcome_history([
        anchor_cli.normalize_outcome_entry({
            "id": "out-1",
            "timestamp": "2026-06-27T02:00:00+00:00",
            "type": "finding",
            "status": "accepted",
            "target": "enzyme",
            "run_id": "run-a",
            "report_id": "imm-1",
            "lesson": "complete PoC wins trust",
        }),
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T01:00:00+00:00",
            "stage": "benchmark_published",
            "target": "damn-vulnerable-defi",
            "run_id": "dvd-run",
            "note": "published scaffold",
        }),
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T03:00:00+00:00",
            "type": "pr",
            "status": "merged",
            "target": "openzeppelin-contracts",
            "run_id": "pr-1",
            "report_id": "6584",
            "lesson": "low level call alignment",
        }),
    ], limit=5)
    assert "TYPE" in rendered
    assert "STATUS" in rendered
    assert rendered.index("benchmark") < rendered.index("pr") < rendered.index("finding")
    assert "published" in rendered


def test_render_outcome_summary_aggregates_status_and_lessons():
    rendered = anchor_cli.render_outcome_summary([
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T02:00:00+00:00",
            "type": "finding",
            "status": "accepted",
            "target": "enzyme",
            "lesson": "complete PoC wins trust",
        }),
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T01:00:00+00:00",
            "type": "pr",
            "status": "merged",
            "target": "solmate",
            "lesson": "smaller diffs land faster",
        }),
    ], lesson_limit=5)
    assert "Outcome summary" in rendered
    assert "accepted=1" in rendered
    assert "merged=1" in rendered
    assert "enzyme: 1 event(s)" in rendered
    assert "complete PoC wins trust" in rendered


def test_render_outcome_insights_highlights_top_lessons():
    rendered = anchor_cli.render_outcome_insights([
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T03:00:00+00:00",
            "type": "finding",
            "status": "rejected",
            "target": "enzyme",
            "lesson": "Missing reproduction evidence",
        }),
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T02:00:00+00:00",
            "type": "finding",
            "status": "accepted",
            "target": "enzyme",
            "lesson": "Missing reproduction evidence",
        }),
        anchor_cli.normalize_outcome_entry({
            "timestamp": "2026-06-27T01:00:00+00:00",
            "type": "issue",
            "status": "open",
            "target": "solmate",
            "lesson": "Environment mismatch",
        }),
    ], limit=50, top_n=5)
    assert "Last 3 outcomes" in rendered
    assert "rejected: 1" in rendered
    assert "accepted: 1" in rendered
    assert "Missing reproduction evidence (2)" in rendered
    assert "enzyme: 2" in rendered
    assert "Lessons learned (grouped)" in rendered


def test_hunt_planner_builds_target_specific_plan(tmp_path):
    target_path = tmp_path / "targets" / "enzyme-blue.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text(
        "# Enzyme Blue Hunt Plan\n\n"
        "## Chosen target\n\n"
        "`UnpermissionedActionsWrapper`\n\n"
        "## Why this is the solid win\n\n"
        "- Authorization flaws tend to have a clean reproduction path.\n"
    )

    payload = hunt_planner.build_hunt_plan(
        target_path=target_path,
        root=tmp_path,
        benchmark_entries=[],
        outcome_entries=[],
        program="Enzyme",
        contract="UnpermissionedActionsWrapper",
    )

    assert payload["target"]["contract"] == "UnpermissionedActionsWrapper"
    assert "Authorization Boundary Review" in payload["hunt_for"][0]
    assert payload["hypothesis_templates"][0]["claim"]
    rendered = hunt_planner.render_hunt_plan(payload)
    assert "Hunt Plan" in rendered
    assert "What to hunt for" in rendered
    assert "How to hunt" in rendered
    assert "Evidence requirements" in rendered


def test_cmd_benchmark_publish_updates_manifest_and_ledger(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "index.json"
    ledger_path = tmp_path / "ledger.jsonl"
    outcomes_dir = tmp_path / "outcomes"

    prev_dir = tmp_path / "benchmarks" / "damn-vulnerable-defi" / "runs" / "run-prev"
    prev_dir.mkdir(parents=True)
    prev_storage_path = prev_dir / "storage.json"
    prev_storage_path.write_text(json.dumps({"status": "published", "signature_state": "signed"}))
    (prev_dir / "README.md").write_text("# run-prev\n")
    (prev_dir / "benchmark.json").write_text(json.dumps({
        "summary": {"passed": 1, "failed": 1, "timed_out": 0, "detector_signals": 1, "raw_detector_findings": 4, "target_relevant_detector_findings": 4, "medium_high_target_relevant_findings": 1},
        "results": [
            {"challenge": "alpha", "status": "FAILED"},
            {"challenge": "beta", "status": "PASSED"},
        ],
    }))

    run_dir = tmp_path / "benchmarks" / "damn-vulnerable-defi" / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    storage_path = run_dir / "storage.json"
    storage_path.write_text(json.dumps({"status": "ready", "signature_state": "pending"}))
    (run_dir / "README.md").write_text("# run-a\n")
    (run_dir / "benchmark.json").write_text(json.dumps({
        "summary": {"passed": 2, "failed": 0, "timed_out": 0, "detector_signals": 2, "raw_detector_findings": 6, "target_relevant_detector_findings": 5, "medium_high_target_relevant_findings": 2},
        "results": [
            {"challenge": "alpha", "status": "PASSED"},
            {"challenge": "beta", "status": "FAILED"},
        ],
    }))
    manifest_path.write_text(json.dumps({
        "history_policy": dict(anchor_cli.DEFAULT_HISTORY_POLICY),
        "benchmarks": [
            {
                "id": "run-prev",
                "target": "damn-vulnerable-defi",
                "executed_at": "2026-06-27T00:01:00+00:00",
                "publication_tier": "published",
                "record": str((prev_dir / "README.md").relative_to(tmp_path)),
                "artifact_json": str((prev_dir / "benchmark.json").relative_to(tmp_path)),
                "storage_manifest": str(prev_storage_path.relative_to(tmp_path)),
            },
            {
                "id": "run-a",
                "target": "damn-vulnerable-defi",
                "executed_at": "2026-06-27T00:23:21+00:00",
                "record": str((run_dir / "README.md").relative_to(tmp_path)),
                "artifact_json": str((run_dir / "benchmark.json").relative_to(tmp_path)),
                "storage_manifest": str(storage_path.relative_to(tmp_path)),
            }
        ],
    }))
    monkeypatch.setattr(anchor_cli, "ROOT", tmp_path)
    monkeypatch.setattr(anchor_cli, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(anchor_cli, "OUTCOMES_DIR", outcomes_dir)
    monkeypatch.setattr(anchor_cli, "OUTCOME_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(anchor_cli, "utcnow_iso", lambda: "2026-06-27T01:00:00+00:00")

    rc = anchor_cli.cmd_benchmark_publish(type("Args", (), {"run_id": "run-a", "note": "phase1 ready"}))
    assert rc == 0

    payload = json.loads(manifest_path.read_text())
    entry = next(item for item in payload["benchmarks"] if item["id"] == "run-a")
    assert entry["publication_tier"] == "published"
    assert entry["status"] == "published"
    assert entry["published_at"] == "2026-06-27T01:00:00+00:00"
    assert entry["publication_note"] == "phase1 ready"
    assert entry["published_record"].endswith("PUBLISHED.md")
    assert entry["regression_report"].endswith("REGRESSION_REPORT.md")

    storage_payload = json.loads(storage_path.read_text())
    assert storage_payload["status"] == "published"
    assert storage_payload["published_at"] == "2026-06-27T01:00:00+00:00"

    report_path = tmp_path / entry["regression_report"]
    report_text = report_path.read_text()
    assert "Benchmark Regression Report" in report_text
    assert "Resolved" in report_text
    assert "Regressions" in report_text
    assert "alpha" in report_text
    assert "beta" in report_text

    ledger_entries = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    assert ledger_entries[0]["type"] == "benchmark"
    assert ledger_entries[0]["status"] == "published"
    assert ledger_entries[0]["run_id"] == "run-a"
    assert ledger_entries[0]["links"]["benchmark"] == str((run_dir / "README.md").relative_to(tmp_path))
    assert ledger_entries[0]["links"]["artifact"].endswith("PUBLISHED.md")
    assert ledger_entries[0]["links"]["report"].endswith("REGRESSION_REPORT.md")

    out = capsys.readouterr().out
    assert "Published benchmark run: run-a" in out

def test_cmd_outcome_add_appends_ledger(tmp_path, monkeypatch, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    outcomes_dir = tmp_path / "outcomes"
    monkeypatch.setattr(anchor_cli, "OUTCOMES_DIR", outcomes_dir)
    monkeypatch.setattr(anchor_cli, "OUTCOME_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(anchor_cli, "utcnow_iso", lambda: "2026-06-27T02:00:00+00:00")

    rc = anchor_cli.cmd_outcome_add(type("Args", (), {
        "id": "out-1",
        "type": "finding",
        "status": "accepted",
        "target": "enzyme",
        "run_id": "run-a",
        "benchmark_id": "bench-a",
        "claim_id": "claim-a",
        "case_id": "case-1",
        "report_id": "immunefi-42",
        "evidence": "benchmarks/dvd/run-a/README.md",
        "lesson": "accepted when reproduction is explicit",
        "link_benchmark": "benchmarks/index.json",
        "link_artifact": "artifacts/evidence.json",
        "link_pr": "",
        "link_issue": "",
        "link_report": "https://immunefi.com/report/42",
        "note": "accepted for payout review",
    }))
    assert rc == 0

    ledger_entries = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    assert ledger_entries[0]["id"] == "out-1"
    assert ledger_entries[0]["type"] == "finding"
    assert ledger_entries[0]["status"] == "accepted"
    assert ledger_entries[0]["target"] == "enzyme"
    assert ledger_entries[0]["report_id"] == "immunefi-42"
    assert ledger_entries[0]["lesson"] == "accepted when reproduction is explicit"
    assert ledger_entries[0]["links"]["report"] == "https://immunefi.com/report/42"

    out = capsys.readouterr().out
    assert "Recorded outcome event: finding accepted" in out


def test_script_registry_loader_and_storage_manifest_shape():
    registry = anchor_scripts.load_script_registry()
    summary = anchor_scripts.registry_summary(registry)
    assert summary["script_count"] >= 1
    assert summary["allowed_count"] <= summary["script_count"]
    assert summary["registry_path"].endswith("scripts/registry.json")

    manifest = anchor_storage.build_storage_manifest(
        benchmark_id="dvd-phase1-local",
        run_id="run-123",
        target="damn-vulnerable-defi",
        stage="Phase 1",
        status="scaffold",
        artifact_path="benchmarks/run.json",
        evidence_path="benchmarks/run/evidence",
        manifest_path="benchmarks/run/storage.json",
        ledger_path="outcomes/ledger.jsonl",
        archive_path="benchmarks/run",
    )
    storage = anchor_storage.storage_summary(manifest)
    assert storage["benchmark_id"] == "dvd-phase1-local"
    assert storage["run_id"] == "run-123"
    assert storage["signature_state"] == "pending"
    assert storage["manifest_path"] == "benchmarks/run/storage.json"


def test_scabench_adapter_scores_latest_benchmark():
    score = scabench_adapter.adapt({
        "results_summary": {
            "passed": 10,
            "failed": 2,
            "timed_out": 1,
            "skipped": 1,
            "aligned": 8,
            "detector_signals": 6,
            "investigate": 1,
            "diverged": 0,
            "environment_sensitive": 1,
        },
        "confidence_ladder": {
            "methodology": "high",
            "environment": "high",
            "detection": "partial",
            "reproduction": "partial",
            "comparative_data": "not_yet",
        },
    })
    assert score["adapter"] == "scabench"
    assert 0 <= score["score"] <= 100
    assert score["grade"] in {"A", "B", "C", "D", "E"}
    assert "ScaBench score" in score["summary"]


def test_parser_accepts_knowledge_list():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["knowledge", "list"])
    assert args.command == "knowledge"
    assert args.knowledge_command == "list"


def test_parser_accepts_knowledge_show():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["knowledge", "show", "sarif"])
    assert args.command == "knowledge"
    assert args.knowledge_command == "show"
    assert args.slug == "sarif"


def test_parser_accepts_knowledge_search():
    parser = anchor_cli.create_parser()
    args = parser.parse_args(["knowledge", "search", "promotion gate", "--limit", "3"])
    assert args.command == "knowledge"
    assert args.knowledge_command == "search"
    assert args.query == "promotion gate"
    assert args.limit == 3


def test_parser_accepts_bugbot_train():
    parser = anchor_cli.create_parser()
    args = parser.parse_args([
        "bugbot", "train",
        "--scenario", "scenarios/uups_initializer_takeover.json",
        "--strict-archive",
    ])
    assert args.command == "bugbot"
    assert args.bugbot_command == "train"
    assert args.scenario == "scenarios/uups_initializer_takeover.json"
    assert args.strict_archive is True


def test_load_training_scenarios_accepts_single_object(tmp_path: Path) -> None:
    path = tmp_path / "one.json"
    path.write_text('{"id": "s1", "pass": true}', encoding="utf-8")
    loaded = anchor_cli.load_training_scenarios(path)
    assert loaded == [{"id": "s1", "pass": True}]


def test_cmd_bugbot_train_success(tmp_path: Path, monkeypatch, capsys) -> None:
    scenario = tmp_path / "scenario.json"
    scenario.write_text('{"id": "demo", "pass": true}', encoding="utf-8")
    knowledge_root = tmp_path / "knowledge"
    monkeypatch.setattr(anchor_cli, "ROOT", tmp_path)

    rc = anchor_cli.cmd_bugbot_train(type("Args", (), {
        "scenario": str(scenario),
        "strict_archive": False,
    }))
    out = capsys.readouterr()
    assert rc == 0
    assert "Training: PASS" in out.out
    assert "Scenarios: 1/1 passed" in out.out
    assert "Archive:" in out.out


def test_cmd_bugbot_train_exit_zero_when_archive_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    from unittest.mock import MagicMock

    from knowledge.pipeline import ArchiveResult

    scenario = tmp_path / "scenario.json"
    scenario.write_text('{"id": "demo", "pass": true}', encoding="utf-8")
    pipeline = MagicMock()
    pipeline.archive_training_run.return_value = ArchiveResult(success=False, error="disk full")
    trainer = anchor_cli.BugBotTrainer(pipeline=pipeline)
    monkeypatch.setattr(anchor_cli, "BugBotTrainer", lambda **kwargs: trainer)
    monkeypatch.setattr(anchor_cli, "ROOT", tmp_path)

    rc = anchor_cli.cmd_bugbot_train(type("Args", (), {
        "scenario": str(scenario),
        "strict_archive": False,
    }))
    out = capsys.readouterr()
    assert rc == 0
    assert "Training: PASS" in out.out
    assert "Archive: FAILED (disk full)" in out.err


def test_cmd_bugbot_train_strict_archive_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    from unittest.mock import MagicMock

    from knowledge.pipeline import ArchiveResult

    scenario = tmp_path / "scenario.json"
    scenario.write_text('{"id": "demo", "pass": true}', encoding="utf-8")
    pipeline = MagicMock()
    pipeline.archive_training_run.return_value = ArchiveResult(success=False, error="disk full")
    trainer = anchor_cli.BugBotTrainer(pipeline=pipeline, strict_archive=True)
    monkeypatch.setattr(anchor_cli, "BugBotTrainer", lambda **kwargs: trainer)
    monkeypatch.setattr(anchor_cli, "ROOT", tmp_path)

    rc = anchor_cli.cmd_bugbot_train(type("Args", (), {
        "scenario": str(scenario),
        "strict_archive": True,
    }))
    out = capsys.readouterr()
    assert rc == 1
    assert "Training: FAIL" in out.err
    assert "archival failed" in out.err.lower()


def test_parser_accepts_bugbot_scope_check_and_analyze() -> None:
    parser = anchor_cli.create_parser()
    scope_args = parser.parse_args([
        "bugbot", "scope-check",
        "--confirmation", "scope/confirmations/example.md",
    ])
    assert scope_args.bugbot_command == "scope-check"
    assert scope_args.confirmation == "scope/confirmations/example.md"

    analyze_args = parser.parse_args([
        "bugbot", "analyze",
        "--target-id", "dvd-local-lab",
        "--target-ref", "abc123",
    ])
    assert analyze_args.bugbot_command == "analyze"
    assert analyze_args.target_id == "dvd-local-lab"
    assert analyze_args.target_ref == "abc123"


def test_cmd_bugbot_scope_check_issues_grant(tmp_path: Path, monkeypatch, capsys) -> None:
    anchor = tmp_path
    evidence = anchor / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    confirmation = anchor / "confirmation.md"
    fixtures = Path(__file__).resolve().parent / "fixtures"
    confirmation.write_text(
        fixtures.joinpath("scope_confirmation_valid.md").read_text(encoding="utf-8").replace(
            "tests/fixtures/scope_evidence.md",
            "evidence.md",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(anchor_cli, "ROOT", anchor)
    monkeypatch.setenv("ANCHOR_ROOT", str(anchor))

    rc = anchor_cli.cmd_bugbot_scope_check(type("Args", (), {"confirmation": str(confirmation)}))
    out = capsys.readouterr()
    assert rc == 0
    assert "Scope grant active:" in out.out


def test_cmd_bugbot_analyze_denies_without_grant(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ANCHOR_ROOT", str(tmp_path))
    rc = anchor_cli.cmd_bugbot_analyze(type("Args", (), {
        "target_id": "dvd-local-lab",
        "target_ref": "abc123",
        "repo_url": None,
        "workspace": None,
    }))
    out = capsys.readouterr()
    assert rc == 1
    assert "NOT AUTHORIZED" in out.err


def test_cmd_bugbot_analyze_runs_stages_with_grant(tmp_path: Path, monkeypatch, capsys) -> None:
    anchor = tmp_path
    evidence = anchor / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    confirmation = anchor / "confirmation.md"
    fixtures = Path(__file__).resolve().parent / "fixtures"
    confirmation.write_text(
        fixtures.joinpath("scope_confirmation_valid.md").read_text(encoding="utf-8").replace(
            "tests/fixtures/scope_evidence.md",
            "evidence.md",
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ANCHOR_ROOT", str(anchor))
    assert anchor_cli.cmd_bugbot_scope_check(type("Args", (), {"confirmation": str(confirmation)})) == 0

    workspace = anchor / "lab"
    workspace.mkdir()
    (workspace / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "Token.sol").write_text("// sol", encoding="utf-8")

    rc = anchor_cli.cmd_bugbot_analyze(type("Args", (), {
        "target_id": "dvd-local-lab",
        "target_ref": "abc123def4567890abcdef1234567890abcdef12",
        "repo_url": None,
        "workspace": str(workspace),
    }))
    out = capsys.readouterr()
    assert rc == 0
    assert "Analysis: PASS" in out.out
    assert "INSPECT: PASS" in out.out
    assert "Archive:" in out.out



def test_anchor_codex_mcp_print_config_matches_launcher():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    venv_python = ROOT / ".venv" / "bin" / "python"
    python = str(venv_python) if venv_python.is_file() else env.get("PYTHON", "python3")
    anchor_proc = subprocess.run(
        [str(ROOT / "anchor"), "codex", "mcp", "--print-config"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    launcher_proc = subprocess.run(
        [python, "scripts/codex_mcp_launcher.py", "--print-config"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert anchor_proc.returncode == 0
    assert launcher_proc.returncode == 0
    assert json.loads(anchor_proc.stdout) == json.loads(launcher_proc.stdout)
