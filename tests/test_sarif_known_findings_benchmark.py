from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


benchmark = load_module("sarif_known_findings_benchmark", "benchmarks/sarif-known-findings/run_known_findings_benchmark.py")


def test_corpus_has_expected_case_mix():
    cases = benchmark.load_corpus()
    ids = [case["id"] for case in cases]
    assert ids == [
        "duplicate-owner-check",
        "halmos-balance-invariant",
        "generic-source-warning",
        "reentrancy-benign-miss",
    ]
    assert sum(1 for case in cases if case["expected_visible"]) == 3
    assert sum(1 for case in cases if not case["expected_visible"]) == 1


def test_run_benchmark_writes_metrics_and_report(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(benchmark, "FAMILY_DIR", tmp_path)
    monkeypatch.setattr(benchmark, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(benchmark, "CORPUS_PATH", ROOT / "benchmarks" / "sarif-known-findings" / "inputs" / "corpus.json")
    monkeypatch.setattr(benchmark, "EXPECTED_PATH", ROOT / "benchmarks" / "sarif-known-findings" / "expected" / "expectations.json")
    monkeypatch.setattr(benchmark, "MANIFEST_PATH", tmp_path / "index.json")
    monkeypatch.setattr(benchmark, "ROOT_REPORT_PATH", tmp_path / "REPORT.md")

    payload = benchmark.run_benchmark(now=__import__("datetime").datetime(2026, 6, 28, 12, 0, tzinfo=__import__("datetime").timezone.utc))

    run_dir = tmp_path / "runs" / "2026-06-28T12-00-00Z"
    benchmark_json = json.loads((run_dir / "benchmark.json").read_text())
    metrics_json = json.loads((run_dir / "metrics.json").read_text())
    report = (run_dir / "REPORT.md").read_text()
    root_report = (tmp_path / "REPORT.md").read_text()
    manifest = json.loads((tmp_path / "index.json").read_text())

    assert payload["results_summary"]["duplicates_removed"] >= 1
    assert payload["results_summary"]["passed"] + payload["results_summary"]["failed"] == 4
    assert payload["results_summary"]["true_positives"] >= 1
    assert payload["results_summary"]["false_positives"] >= 0
    assert payload["results_summary"]["false_negatives"] >= 0
    assert benchmark_json["results_summary"] == payload["results_summary"]
    assert metrics_json["benchmark"] == "sarif-known-findings"
    assert metrics_json["run_id"] == "sarif-known-findings-2026-06-28T12-00-00Z"
    assert metrics_json["counts"]["true_positive"] == payload["results_summary"]["true_positives"]
    assert metrics_json["metrics"]["precision"] == payload["results_summary"]["precision"]
    assert metrics_json["source_commit"]
    assert metrics_json["runtime_seconds"] == 0
    assert metrics_json["tool_versions"] == {}
    assert "SARIF Known Findings Report" in report
    assert "precision" in report
    assert "regression_kind" in report
    assert "SARIF Known Findings" in root_report
    assert "Metrics JSON" in root_report
    assert manifest["benchmarks"][-1]["id"] == payload["run_id"]
