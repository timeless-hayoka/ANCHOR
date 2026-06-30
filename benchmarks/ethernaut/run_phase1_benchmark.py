#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from anchor_storage import build_storage_manifest, evidence_dir, storage_manifest_path, storage_summary, write_json
from evidence_schema import enrich_benchmark_artifact

ANCHOR_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_ROOT = ANCHOR_ROOT / "benchmarks"
RUNS_ROOT = BENCHMARKS_ROOT / "ethernaut" / "runs"
INDEX_PATH = Path(__file__).with_name("index.json")
MANIFEST_PATH = BENCHMARKS_ROOT / "index.json"
LABEL = "ethernaut-phase1-local"


def rel_to_anchor(path: Path) -> str:
    return str(path.resolve().relative_to(ANCHOR_ROOT))


def load_index() -> dict:
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    payload.setdefault("levels", [])
    return payload


def load_manifest_payload() -> dict:
    if MANIFEST_PATH.exists():
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        payload = {"benchmarks": []}
    payload.setdefault("benchmarks", [])
    payload.setdefault(
        "history_policy",
        {
            "artifact_retention": "keep_all_successful_runs",
            "manifest_default_tier": "development",
            "default_history_view": "published_only",
            "published_tier": "published",
        },
    )
    return payload


def update_manifest(entry: dict) -> dict:
    payload = load_manifest_payload()
    benchmarks = [item for item in payload.get("benchmarks", []) if item.get("id") != entry["id"]]
    benchmarks.append(entry)
    benchmarks.sort(key=lambda item: item.get("executed_at", ""))
    payload["benchmarks"] = benchmarks
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    """
    Create a scaffold Ethernaut benchmark run and update the benchmarks index.
    
    Writes the run's benchmark artifact, storage manifest, evidence directory, and README, then records the run in the persistent benchmarks manifest.
    
    Returns:
        int: `0` when the run is created successfully.
    """
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = RUNS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_root = evidence_dir(run_dir)
    evidence_root.mkdir(parents=True, exist_ok=True)

    index = load_index()
    levels = index.get("levels", [])
    results = []
    for level in levels:
        results.append(
            {
                "level_id": level.get("level_id", "unknown"),
                "name": level.get("name", level.get("level_id", "unknown")),
                "category": level.get("category", "unknown"),
                "status": "PENDING",
                "validation_state": "NOT_TESTED",
                "notes": "Ethernaut runner scaffold; reproduction harness to be populated next.",
            }
        )

    summary = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "timed_out": 0,
        "aligned": 0,
        "environment_sensitive": 0,
        "investigate": 0,
        "diverged": 0,
        "detector_signals": 0,
        "raw_detector_findings": 0,
        "target_relevant_detector_findings": 0,
        "medium_high_target_relevant_findings": 0,
    }

    payload = {
        "schema_version": "1.0",
        "benchmark_id": LABEL,
        "level": "Phase 1 scaffold",
        "executed_at": now.isoformat(),
        "target": {
            "repo": "Ethernaut",
            "index_path": rel_to_anchor(INDEX_PATH),
        },
        "summary": summary,
        "results": results,
    }

    json_path = run_dir / "benchmark.json"
    payload = enrich_benchmark_artifact(payload, artifact_path=rel_to_anchor(json_path))
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    storage_json_path = storage_manifest_path(run_dir)
    storage_manifest = build_storage_manifest(
        benchmark_id=LABEL,
        run_id=f"{LABEL}-{stamp}",
        target="ethernaut",
        stage="Phase 1",
        status="scaffold",
        created_at=payload["executed_at"],
        artifact_type="benchmark_run",
        artifact_path=rel_to_anchor(json_path),
        evidence_path=rel_to_anchor(evidence_root),
        manifest_path=rel_to_anchor(storage_json_path),
        ledger_path=rel_to_anchor(ANCHOR_ROOT / "outcomes" / "ledger.jsonl"),
        archive_path=rel_to_anchor(run_dir),
        signature_state="pending",
    )
    write_json(storage_json_path, storage_manifest)

    manifest_entry = {
        "id": f"{LABEL}-{stamp}",
        "target": "ethernaut",
        "title": "Ethernaut Phase 1 scaffold run",
        "status": "scaffold",
        "level": "Phase 1",
        "publication_tier": "development",
        "executed_at": payload["executed_at"],
        "record": rel_to_anchor(run_dir / "README.md"),
        "artifact_json": rel_to_anchor(json_path),
        "storage_manifest": rel_to_anchor(storage_json_path),
        "storage": storage_summary(storage_manifest),
        "storage_status": "ready",
        "evidence_path": rel_to_anchor(evidence_root),
        "signature_state": storage_manifest["signature_state"],
        "results_summary": summary,
        "confidence": "scaffold",
        "confidence_ladder": {
            "methodology": "high",
            "environment": "high",
            "detection": "not_yet",
            "reproduction": "not_yet",
            "comparative_data": "not_yet",
        },
    }

    md_path = run_dir / "README.md"
    md_path.write_text(
        f"# Ethernaut Phase 1 Scaffold Run - {stamp}\n\n"
        f"- Benchmark ID: `{LABEL}`\n"
        f"- Executed at: `{payload['executed_at']}`\n"
        f"- Levels indexed: `{len(levels)}`\n"
        f"- Evidence root: `{rel_to_anchor(evidence_root)}`\n"
        f"- Storage manifest: `{rel_to_anchor(storage_json_path)}`\n",
        encoding="utf-8",
    )

    manifest_entry["record"] = rel_to_anchor(md_path)
    manifest = update_manifest(manifest_entry)
    latest = max(manifest["benchmarks"], key=lambda item: item.get("executed_at", "")) if manifest.get("benchmarks") else None
    print(f"Created Ethernaut scaffold run: {latest['id'] if latest else manifest_entry['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
