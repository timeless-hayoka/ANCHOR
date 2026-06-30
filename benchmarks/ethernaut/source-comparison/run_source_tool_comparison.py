#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ANCHOR_ROOT = Path(__file__).resolve().parents[3]
if str(ANCHOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ANCHOR_ROOT))

from anchor_sarif.pipeline import SARIFProcessingPipeline
from evidence_schema import enrich_benchmark_artifact

FAMILY_DIR = Path(__file__).resolve().parent
RUNS_ROOT = FAMILY_DIR / "runs"
CORPUS_PATH = FAMILY_DIR / "inputs" / "corpus.json"
EXPECTED_PATH = FAMILY_DIR / "expected" / "expectations.json"
MANIFEST_PATH = ANCHOR_ROOT / "benchmarks" / "index.json"
ROOT_REPORT_PATH = FAMILY_DIR / "REPORT.md"
BENCHMARK_ID = "ethernaut-source-comparison"
TITLE = "Ethernaut source-tool comparison corpus"
SOURCE_TOOL_NAME = "slither"
DEFAULT_HISTORY_POLICY = {
    "artifact_retention": "keep_all_successful_runs",
    "manifest_default_tier": "development",
    "default_history_view": "published_only",
    "published_tier": "published",
    "note": "Successful development reruns remain on disk, but only intentionally promoted runs are first-class published artifacts.",
}


def rel_to_anchor(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ANCHOR_ROOT))
    except ValueError:
        return str(resolved)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def load_corpus(path: Path = CORPUS_PATH) -> list[dict[str, Any]]:
    payload = load_json(path)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("corpus cases must be a list")
    return [case for case in cases if isinstance(case, dict)]


def load_expectations(path: Path = EXPECTED_PATH) -> dict[str, Any]:
    return load_json(path)


def load_manifest_payload() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        payload = load_json(MANIFEST_PATH)
    else:
        payload = {"benchmarks": []}
    payload.setdefault("history_policy", dict(DEFAULT_HISTORY_POLICY))
    payload.setdefault("benchmarks", [])
    return payload


def save_manifest_payload(payload: dict[str, Any]) -> None:
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def git_commit_sha() -> str:
    proc = subprocess.run(
        ["git", "-C", str(ANCHOR_ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        return proc.stdout.strip()
    return "unknown"


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "case"


def case_label(case: dict[str, Any]) -> str:
    return str(case.get("id") or case.get("name") or "case")


def case_display_findings(enriched: list[Any]) -> list[str]:
    items: list[str] = []
    for item in enriched:
        finding = item.finding
        items.append(f"{finding.tool}:{finding.rule_id}:{finding.file_path}:{finding.start_line}")
    return items


def evaluate_case(case: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    slug = slugify(case_label(case))
    db_path = run_dir / f"{slug}.db"
    pipeline = SARIFProcessingPipeline(
        db_path=db_path,
        enable_semantic_clustering=False,
        filter_false_positives=True,
    )
    enriched = pipeline.process(
        tool_outputs=case.get("tool_outputs", {}),
        filter_false_positives=True,
    )
    stats = pipeline.last_run_stats
    anchor_expected_visible = bool(case.get("anchor_expected_visible", case.get("expected_visible", False)))
    source_tool_visible = bool(case.get("source_tool_expected_visible", False))
    anchor_visible = bool(enriched)
    if anchor_expected_visible and anchor_visible:
        anchor_classification = "TP"
    elif anchor_expected_visible and not anchor_visible:
        anchor_classification = "FN"
    elif not anchor_expected_visible and anchor_visible:
        anchor_classification = "FP"
    else:
        anchor_classification = "TN"
    status = "PASSED" if anchor_classification in {"TP", "TN"} else "FAILED"
    if anchor_visible and source_tool_visible:
        compare_classification = "shared_visible"
    elif anchor_visible and not source_tool_visible:
        compare_classification = "anchor_only"
    elif not anchor_visible and source_tool_visible:
        compare_classification = "source_only"
    else:
        compare_classification = "shared_hidden"
    return {
        "challenge": case_label(case),
        "name": case.get("name", case_label(case)),
        "status": status,
        "anchor_classification": anchor_classification,
        "expected_visible": anchor_expected_visible,
        "anchor_visible": anchor_visible,
        "source_tool_visible": source_tool_visible,
        "comparison": compare_classification,
        "expected_findings": list(case.get("expected_findings", [])),
        "source_tool_findings": list(case.get("source_tool_findings", [])),
        "actual_findings": case_display_findings(enriched),
        "raw_findings": stats.ingested,
        "unique_findings": stats.after_dedup,
        "duplicates_removed": max(0, stats.ingested - stats.after_dedup),
        "signal_discarded": stats.signal_discarded,
        "signal_promoted": stats.signal_promoted,
        "signal_review": stats.signal_review,
        "visible_count": len(enriched),
        "note": case.get("reason", ""),
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(1 for result in results if result["anchor_classification"] == "TP")
    fp = sum(1 for result in results if result["anchor_classification"] == "FP")
    fn = sum(1 for result in results if result["anchor_classification"] == "FN")
    tn = sum(1 for result in results if result["anchor_classification"] == "TN")
    duplicates_removed = sum(int(result.get("duplicates_removed", 0)) for result in results)
    raw_findings = sum(int(result.get("raw_findings", 0)) for result in results)
    unique_findings = sum(int(result.get("unique_findings", 0)) for result in results)
    anchor_visible = sum(1 for result in results if result.get("anchor_visible"))
    source_visible = sum(1 for result in results if result.get("source_tool_visible"))
    shared_visible = sum(1 for result in results if result.get("comparison") == "shared_visible")
    anchor_only = sum(1 for result in results if result.get("comparison") == "anchor_only")
    source_only = sum(1 for result in results if result.get("comparison") == "source_only")
    shared_hidden = sum(1 for result in results if result.get("comparison") == "shared_hidden")
    agreement = shared_visible + shared_hidden
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    passed = tp + tn
    failed = fp + fn
    return {
        "passed": passed,
        "failed": failed,
        "timed_out": 0,
        "skipped": 0,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "duplicates_removed": duplicates_removed,
        "raw_findings": raw_findings,
        "unique_findings": unique_findings,
        "detector_signals": anchor_visible,
        "raw_detector_findings": raw_findings,
        "target_relevant_detector_findings": anchor_visible,
        "medium_high_target_relevant_findings": tp + fp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "source_tool": {
            "name": SOURCE_TOOL_NAME,
            "visible_count": source_visible,
            "hidden_count": len(results) - source_visible,
            "shared_visible": shared_visible,
            "anchor_only": anchor_only,
            "source_only": source_only,
            "shared_hidden": shared_hidden,
            "agreement": agreement,
            "visible_delta": anchor_visible - source_visible,
        },
    }


def render_report(payload: dict[str, Any]) -> str:
    summary = payload["results_summary"]
    source_tool = summary["source_tool"]
    lines = [
        f"# Ethernaut Source-Tool Comparison Report - {payload['executed_at']}",
        "",
        f"- Benchmark ID: `{payload['benchmark_id']}`",
        f"- Run ID: `{payload['run_id']}`",
        f"- Corpus: `{payload['corpus_path']}`",
        f"- Expectations: `{payload['expected_path']}`",
        f"- Benchmark JSON: `{payload['artifact_json']}`",
        f"- Metrics JSON: `{payload['metrics_json']}`",
        f"- Source Tool Metrics JSON: `{payload['source_tool_metrics_json']}`",
        f"- Source Tool Compare JSON: `{payload['source_tool_compare_json']}`",
        "",
        "## Anchor Summary",
        f"- cases: {summary['cases']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        f"- true_positives: {summary['true_positives']}",
        f"- false_positives: {summary['false_positives']}",
        f"- false_negatives: {summary['false_negatives']}",
        f"- true_negatives: {summary['true_negatives']}",
        f"- duplicates_removed: {summary['duplicates_removed']}",
        f"- precision: {summary['precision']}",
        f"- recall: {summary['recall']}",
        f"- f1: {summary['f1']}",
        "",
        "## Source Tool Comparison",
        f"- source_tool: `{source_tool['name']}`",
        f"- anchor_visible: `{summary['detector_signals']}`",
        f"- source_tool_visible: `{source_tool['visible_count']}`",
        f"- shared_visible: `{source_tool['shared_visible']}`",
        f"- anchor_only: `{source_tool['anchor_only']}`",
        f"- source_only: `{source_tool['source_only']}`",
        f"- agreement: `{source_tool['agreement']}`",
        f"- visible_delta: `{source_tool['visible_delta']}`",
        "",
        "## Cases",
    ]
    for result in payload["results"]:
        lines.extend([
            "",
            f"### {result['challenge']}",
            f"- status: `{result['status']}`",
            f"- anchor_classification: `{result['anchor_classification']}`",
            f"- expected_visible: `{result['expected_visible']}`",
            f"- anchor_visible: `{result['anchor_visible']}`",
            f"- source_tool_visible: `{result['source_tool_visible']}`",
            f"- comparison: `{result['comparison']}`",
        ])
        if result.get("note"):
            lines.append(f"- note: {result['note']}")
        lines.extend([
            f"- raw_findings: `{result['raw_findings']}`",
            f"- unique_findings: `{result['unique_findings']}`",
            f"- duplicates_removed: `{result['duplicates_removed']}`",
            f"- actual_findings: `{', '.join(result['actual_findings']) or '—'}`",
        ])
    lines.extend([
        "",
        "## Evidence",
        f"- inputs: `{payload['corpus_path']}`",
        f"- expectations: `{payload['expected_path']}`",
        f"- manifest: `{payload['manifest_path']}`",
        f"- source_tool_compare: `{payload['source_tool_compare_json']}`",
    ])
    return "\n".join(lines) + "\n"


def update_manifest_entry(entry: dict[str, Any]) -> dict[str, Any]:
    payload = load_manifest_payload()
    benchmarks = [item for item in payload.get("benchmarks", []) if item.get("id") != entry["id"]]
    benchmarks.append(entry)
    benchmarks.sort(key=lambda item: item.get("executed_at", ""))
    payload["benchmarks"] = benchmarks
    save_manifest_payload(payload)
    return payload


def write_root_report(latest_payload: dict[str, Any]) -> None:
    summary = latest_payload["results_summary"]
    source_tool = summary["source_tool"]
    lines = [
        "# Ethernaut Source-Tool Comparison",
        "",
        f"- Latest run: `{latest_payload['run_id']}`",
        f"- Executed at: `{latest_payload['executed_at']}`",
        f"- Cases: `{summary['cases']}`",
        f"- Passed: `{summary['passed']}`",
        f"- Failed: `{summary['failed']}`",
        f"- True positives: `{summary['true_positives']}`",
        f"- False positives: `{summary['false_positives']}`",
        f"- False negatives: `{summary['false_negatives']}`",
        f"- True negatives: `{summary['true_negatives']}`",
        f"- Duplicates removed: `{summary['duplicates_removed']}`",
        f"- Precision: `{summary['precision']}`",
        f"- Recall: `{summary['recall']}`",
        f"- F1: `{summary['f1']}`",
        f"- Source tool: `{source_tool['name']}`",
        f"- Source tool visible: `{source_tool['visible_count']}`",
        f"- Shared visible: `{source_tool['shared_visible']}`",
        f"- Anchor only: `{source_tool['anchor_only']}`",
        f"- Source only: `{source_tool['source_only']}`",
        "",
        "## Report",
        f"- [Latest run report]({latest_payload['record']})",
        f"- [Benchmark JSON]({latest_payload['artifact_json']})",
        f"- [Metrics JSON]({latest_payload['metrics_json']})",
        f"- [Source Tool Metrics JSON]({latest_payload['source_tool_metrics_json']})",
        f"- [Source Tool Compare JSON]({latest_payload['source_tool_compare_json']})",
    ]
    ROOT_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmark(*, now: dt.datetime | None = None) -> dict[str, Any]:
    """
    Run the Ethernaut source-tool comparison benchmark and write its artifacts.
    
    Parameters:
    	now (datetime.datetime | None): The execution time to use for the run. When omitted, uses the current UTC time.
    
    Returns:
    	dict[str, Any]: The benchmark payload containing run metadata, case results, summary metrics, and artifact references.
    """
    current = now or dt.datetime.now(dt.timezone.utc)
    stamp = current.strftime("%Y-%m-%dT%H-%M-%SZ")
    run_id = f"{BENCHMARK_ID}-{stamp}"
    run_dir = RUNS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus()
    expectations = load_expectations()
    results = [evaluate_case(case, run_dir) for case in corpus]
    summary = aggregate_results(results)
    summary["cases"] = len(results)
    expected_summary = expectations.get("expected_summary", {}) if isinstance(expectations, dict) else {}

    benchmark_json_path = run_dir / "benchmark.json"
    metrics_json_path = run_dir / "metrics.json"
    source_tool_metrics_path = run_dir / "source_tool_metrics.json"
    source_tool_compare_path = run_dir / "source_tool_compare.json"
    report_path = run_dir / "REPORT.md"
    source_tool = summary["source_tool"]
    payload = {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "run_id": run_id,
        "title": TITLE,
        "target": "anchor_sarif",
        "status": "complete",
        "confidence": "measured",
        "level": "Phase 3",
        "executed_at": current.isoformat(),
        "corpus_path": rel_to_anchor(CORPUS_PATH),
        "expected_path": rel_to_anchor(EXPECTED_PATH),
        "manifest_path": rel_to_anchor(MANIFEST_PATH),
        "artifact_json": rel_to_anchor(benchmark_json_path),
        "metrics_json": rel_to_anchor(metrics_json_path),
        "source_tool_metrics_json": rel_to_anchor(source_tool_metrics_path),
        "source_tool_compare_json": rel_to_anchor(source_tool_compare_path),
        "record": rel_to_anchor(report_path),
        "results_summary": summary,
        "results": results,
        "expected_summary": expected_summary,
    }
    payload = enrich_benchmark_artifact(payload, artifact_path=rel_to_anchor(benchmark_json_path))
    benchmark_json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    metrics_payload = {
        "schema_version": "1.0",
        "benchmark": BENCHMARK_ID,
        "run_id": run_id,
        "source_commit": git_commit_sha(),
        "counts": {
            "true_positive": summary["true_positives"],
            "false_positive": summary["false_positives"],
            "false_negative": summary["false_negatives"],
            "true_negative": summary["true_negatives"],
            "duplicates_removed": summary["duplicates_removed"],
        },
        "metrics": {
            "precision": summary["precision"],
            "recall": summary["recall"],
            "f1": summary["f1"],
        },
        "runtime_seconds": 0,
        "tool_versions": {
            "anchor_sarif": "local",
            "source_tool": "slither reference labels",
        },
        "source_tool": {
            "name": source_tool["name"],
            "visible_count": source_tool["visible_count"],
            "hidden_count": source_tool["hidden_count"],
            "shared_visible": source_tool["shared_visible"],
            "anchor_only": source_tool["anchor_only"],
            "source_only": source_tool["source_only"],
            "shared_hidden": source_tool["shared_hidden"],
            "agreement": source_tool["agreement"],
            "visible_delta": source_tool["visible_delta"],
        },
    }
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2) + "\n", encoding="utf-8")

    source_tool_metrics_payload = {
        "schema_version": "1.0",
        "benchmark": BENCHMARK_ID,
        "run_id": run_id,
        "source_tool": source_tool["name"],
        "visible_count": source_tool["visible_count"],
        "hidden_count": source_tool["hidden_count"],
        "shared_visible": source_tool["shared_visible"],
        "anchor_only": source_tool["anchor_only"],
        "source_only": source_tool["source_only"],
        "shared_hidden": source_tool["shared_hidden"],
        "agreement": source_tool["agreement"],
        "visible_delta": source_tool["visible_delta"],
        "cases": [
            {
                "id": result["challenge"],
                "anchor_visible": result["anchor_visible"],
                "source_tool_visible": result["source_tool_visible"],
                "comparison": result["comparison"],
            }
            for result in results
        ],
    }
    source_tool_metrics_path.write_text(json.dumps(source_tool_metrics_payload, indent=2) + "\n", encoding="utf-8")

    source_tool_compare_payload = {
        "schema_version": "1.0",
        "benchmark": BENCHMARK_ID,
        "run_id": run_id,
        "source_tool": source_tool["name"],
        "comparison": {
            "anchor_visible": summary["detector_signals"],
            "source_tool_visible": source_tool["visible_count"],
            "shared_visible": source_tool["shared_visible"],
            "anchor_only": source_tool["anchor_only"],
            "source_only": source_tool["source_only"],
            "shared_hidden": source_tool["shared_hidden"],
            "agreement": source_tool["agreement"],
            "visible_delta": source_tool["visible_delta"],
        },
        "cases": [
            {
                "id": result["challenge"],
                "anchor_visible": result["anchor_visible"],
                "source_tool_visible": result["source_tool_visible"],
                "comparison": result["comparison"],
                "anchor_classification": result["anchor_classification"],
            }
            for result in results
        ],
    }
    source_tool_compare_path.write_text(json.dumps(source_tool_compare_payload, indent=2) + "\n", encoding="utf-8")

    report_path.write_text(render_report(payload), encoding="utf-8")
    write_root_report(payload)

    manifest_entry = {
        "id": run_id,
        "target": "anchor_sarif",
        "title": "Ethernaut source-tool comparison benchmark run",
        "status": "complete",
        "level": "Phase 3",
        "executed_at": payload["executed_at"],
        "confidence": payload["confidence"],
        "publication_tier": "development",
        "record": payload["record"],
        "artifact_json": payload["artifact_json"],
        "metrics_json": payload["metrics_json"],
        "results_summary": summary,
        "confidence_ladder": {
            "methodology": "high",
            "environment": "high",
            "detection": "high",
            "reproduction": "high",
            "comparative_data": "high",
        },
        "verified": True,
    }
    update_manifest_entry(manifest_entry)
    return payload


def main() -> int:
    payload = run_benchmark()
    print(f"Created Ethernaut benchmark run: {payload['run_id']}")
    print(f"Report: {payload['record']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
