from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


benchmark = load_module(
    "defihacklabs_source_tool_comparison",
    "benchmarks/defihacklabs/source-comparison/run_source_tool_comparison.py",
)


def test_corpus_has_source_tool_labels():
    cases = benchmark.load_corpus()
    ids = [case["id"] for case in cases]
    assert ids == [
        "duplicate-owner-check",
        "halmos-balance-invariant",
        "generic-source-warning",
        "reentrancy-benign-miss",
        "source-tool-only-noise",
    ]
    assert sum(1 for case in cases if case["anchor_expected_visible"]) == 3
    assert sum(1 for case in cases if case["source_tool_expected_visible"]) == 4


def test_run_benchmark_writes_compare_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(benchmark, "FAMILY_DIR", tmp_path)
    monkeypatch.setattr(benchmark, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(benchmark, "CORPUS_PATH", ROOT / "benchmarks" / "defihacklabs" / "source-comparison" / "inputs" / "corpus.json")
    monkeypatch.setattr(benchmark, "EXPECTED_PATH", ROOT / "benchmarks" / "defihacklabs" / "source-comparison" / "expected" / "expectations.json")
    monkeypatch.setattr(benchmark, "MANIFEST_PATH", tmp_path / "index.json")
    monkeypatch.setattr(benchmark, "ROOT_REPORT_PATH", tmp_path / "REPORT.md")

    payload = benchmark.run_benchmark(now=datetime(2026, 6, 28, 13, 0, tzinfo=timezone.utc))

    run_dir = tmp_path / "runs" / "2026-06-28T13-00-00Z"
    benchmark_json = json.loads((run_dir / "benchmark.json").read_text())
    metrics_json = json.loads((run_dir / "metrics.json").read_text())
    source_tool_metrics = json.loads((run_dir / "source_tool_metrics.json").read_text())
    source_tool_compare = json.loads((run_dir / "source_tool_compare.json").read_text())
    report = (run_dir / "REPORT.md").read_text()
    root_report = (tmp_path / "REPORT.md").read_text()
    manifest = json.loads((tmp_path / "index.json").read_text())

    assert payload["results_summary"]["cases"] == 5
    assert payload["results_summary"]["true_positives"] == 3
    assert payload["results_summary"]["false_positives"] == 0
    assert payload["results_summary"]["false_negatives"] == 0
    assert payload["results_summary"]["true_negatives"] == 2
    assert payload["results_summary"]["source_tool"]["visible_count"] == 4
    assert payload["results_summary"]["source_tool"]["shared_visible"] == 2
    assert payload["results_summary"]["source_tool"]["anchor_only"] == 1
    assert payload["results_summary"]["source_tool"]["source_only"] == 2

    assert benchmark_json["results_summary"] == payload["results_summary"]
    assert benchmark_json["source_tool_compare_json"].endswith("/runs/2026-06-28T13-00-00Z/source_tool_compare.json")
    assert metrics_json["benchmark"] == "defihacklabs-source-comparison"
    assert metrics_json["counts"]["true_positive"] == 3
    assert metrics_json["counts"]["true_negative"] == 2
    assert metrics_json["metrics"]["precision"] == 1.0
    assert metrics_json["source_tool"]["visible_count"] == 4
    assert metrics_json["source_tool"]["anchor_only"] == 1
    assert metrics_json["source_tool"]["source_only"] == 2
    assert source_tool_metrics["source_tool"] == "slither"
    assert source_tool_metrics["visible_count"] == 4
    assert source_tool_compare["source_tool"] == "slither"
    assert source_tool_compare["comparison"]["shared_visible"] == 2
    assert source_tool_compare["comparison"]["anchor_only"] == 1
    assert source_tool_compare["comparison"]["source_only"] == 2
    assert "Source Tool Comparison" in report
    assert "source_tool_compare.json" in report
    assert "DeFiHackLabs Source-Tool Comparison" in root_report
    assert "Source Tool Metrics JSON" in root_report
    assert manifest["benchmarks"][-1]["id"] == payload["run_id"]
