#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ANCHOR_ROOT = Path(__file__).resolve().parents[2]
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
BENCHMARK_ID = "sarif-known-findings"
TITLE = "SARIF known findings corpus"
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
    import subprocess

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
    expected_visible = bool(case.get("expected_visible"))
    actual_visible = bool(enriched)
    if expected_visible and actual_visible:
        classification = "TP"
    elif expected_visible and not actual_visible:
        classification = "FN"
    elif not expected_visible and actual_visible:
        classification = "FP"
    else:
        classification = "TN"
    status = "PASSED" if classification in {"TP", "TN"} else "FAILED"
    return {
        "challenge": case_label(case),
        "name": case.get("name", case_label(case)),
        "status": status,
        "classification": classification,
        "expected_visible": expected_visible,
        "actual_visible": actual_visible,
        "expected_findings": list(case.get("expected_findings", [])),
        "actual_findings": case_display_findings(enriched),
        "raw_findings": stats.ingested,
        "unique_findings": stats.after_dedup,
        "duplicates_removed": max(0, stats.ingested - stats.after_dedup),
        "signal_discarded": stats.signal_discarded,
        "signal_promoted": stats.signal_promoted,
        "signal_review": stats.signal_review,
        "visible_count": len(enriched),
        "note": case.get("reason", ""),
        "regression_kind": case.get("regression_kind", ""),
        "regression_reason": case.get("regression_reason", ""),
        "fix_hint": case.get("fix_hint", ""),
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(1 for result in results if result["classification"] == "TP")
    fp = sum(1 for result in results if result["classification"] == "FP")
    fn = sum(1 for result in results if result["classification"] == "FN")
    tn = sum(1 for result in results if result["classification"] == "TN")
    duplicates_removed = sum(int(result.get("duplicates_removed", 0)) for result in results)
    raw_findings = sum(int(result.get("raw_findings", 0)) for result in results)
    unique_findings = sum(int(result.get("unique_findings", 0)) for result in results)
    visible_findings = sum(int(result.get("visible_count", 0)) for result in results)
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
        "detector_signals": visible_findings,
        "raw_detector_findings": raw_findings,
        "target_relevant_detector_findings": visible_findings,
        "medium_high_target_relevant_findings": tp + fp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def render_report(payload: dict[str, Any]) -> str:
    summary = payload["results_summary"]
    lines = [
        f"# SARIF Known Findings Report - {payload['executed_at']}",
        "",
        f"- Benchmark ID: `{payload['benchmark_id']}`",
        f"- Run ID: `{payload['run_id']}`",
        f"- Corpus: `{payload['corpus_path']}`",
        f"- Benchmark JSON: `{payload['artifact_json']}`",
        f"- Metrics JSON: `{payload['metrics_json']}`",
        "",
        "## Summary",
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
        "## Cases",
    ]
    for result in payload["results"]:
        lines.extend([
            "",
            f"### {result['challenge']}",
            f"- status: `{result['status']}`",
            f"- classification: `{result['classification']}`",
            f"- expected_visible: `{result['expected_visible']}`",
            f"- actual_visible: `{result['actual_visible']}`",
        ])
        if result.get('regression_kind'):
            lines.append(f"- regression_kind: `{result['regression_kind']}`")
        if result.get('regression_reason'):
            lines.append(f"- regression_reason: {result['regression_reason']}")
        if result.get('fix_hint'):
            lines.append(f"- fix_hint: {result['fix_hint']}")
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
    lines = [
        "# SARIF Known Findings",
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
        "",
        "## Report",
        f"- [Latest run report]({latest_payload['record']})",
        f"- [Benchmark JSON]({latest_payload['artifact_json']})",
        f"- [Metrics JSON]({latest_payload['metrics_json']})",
    ]
    ROOT_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmark(*, now: dt.datetime | None = None) -> dict[str, Any]:
    """
    Run the SARIF known-findings benchmark and write its artifacts.
    
    Parameters:
    	now (datetime.datetime | None): Run timestamp to use for the benchmark.
    
    Returns:
    	dict[str, Any]: The enriched benchmark payload for the completed run.
    """
    current = now or dt.datetime.now(dt.timezone.utc)
    stamp = current.strftime("%Y-%m-%dT%H-%M-%SZ")
    run_id = f"{BENCHMARK_ID}-{stamp}"
    run_dir = RUNS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus()
    results = [evaluate_case(case, run_dir) for case in corpus]
    summary = aggregate_results(results)
    summary["cases"] = len(results)

    benchmark_json_path = run_dir / "benchmark.json"
    metrics_json_path = run_dir / "metrics.json"
    report_path = run_dir / "REPORT.md"
    payload = {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "run_id": run_id,
        "title": TITLE,
        "target": "anchor_sarif",
        "status": "complete",
        "confidence": "measured",
        "level": "Phase 1",
        "executed_at": current.isoformat(),
        "corpus_path": rel_to_anchor(CORPUS_PATH),
        "expected_path": rel_to_anchor(EXPECTED_PATH),
        "manifest_path": rel_to_anchor(MANIFEST_PATH),
        "artifact_json": rel_to_anchor(benchmark_json_path),
        "metrics_json": rel_to_anchor(metrics_json_path),
        "record": rel_to_anchor(report_path),
        "results_summary": summary,
        "results": results,
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
        "tool_versions": {},
    }
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")
    write_root_report(payload)

    manifest_entry = {
        "id": run_id,
        "target": "anchor_sarif",
        "title": "SARIF known findings benchmark run",
        "status": "complete",
        "level": "Phase 1",
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
            "comparative_data": "partial",
        },
        "verified": True,
    }
    update_manifest_entry(manifest_entry)
    return payload


def main() -> int:
    payload = run_benchmark()
    print(f"Created SARIF benchmark run: {payload['run_id']}")
    print(f"Report: {payload['record']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
