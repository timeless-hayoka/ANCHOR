from __future__ import annotations

import importlib.util
import json
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
    assert "benchmarks/damn-vulnerable-defi/runs/new-published/REGRESSION_REPORT.md" in rendered
    assert "benchmarks/damn-vulnerable-defi/runs/new-published/PUBLISHED.md" in rendered
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
