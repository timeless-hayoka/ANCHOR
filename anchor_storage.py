from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BENCHMARKS_ROOT = ROOT / "benchmarks"
OUTCOMES_ROOT = ROOT / "outcomes"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "entry"))
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-") or "entry"


def benchmark_run_dir(benchmark_id: str, run_id: str) -> Path:
    return BENCHMARKS_ROOT / safe_slug(benchmark_id) / "runs" / safe_slug(run_id)


def evidence_dir(run_dir: Path) -> Path:
    return run_dir / "evidence"


def storage_manifest_path(run_dir: Path) -> Path:
    return run_dir / "storage.json"


def build_storage_manifest(
    *,
    benchmark_id: str,
    run_id: str,
    target: str,
    stage: str,
    status: str,
    created_at: str | None = None,
    artifact_type: str = "benchmark_run",
    artifact_path: str = "",
    evidence_path: str = "",
    manifest_path: str = "",
    ledger_path: str = "",
    archive_path: str = "",
    signature_state: str = "pending",
) -> dict[str, Any]:
    created = created_at or utcnow_iso()
    return {
        "schema_version": "1.0",
        "kind": "anchor.storage_manifest",
        "benchmark_id": benchmark_id,
        "run_id": run_id,
        "target": target,
        "stage": stage,
        "status": status,
        "created_at": created,
        "artifact_type": artifact_type,
        "artifact_path": artifact_path,
        "evidence_path": evidence_path,
        "manifest_path": manifest_path,
        "ledger_path": ledger_path,
        "archive_path": archive_path,
        "signature_state": signature_state,
    }


def storage_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_id": manifest.get("benchmark_id", ""),
        "run_id": manifest.get("run_id", ""),
        "target": manifest.get("target", ""),
        "stage": manifest.get("stage", ""),
        "status": manifest.get("status", ""),
        "artifact_path": manifest.get("artifact_path", ""),
        "evidence_path": manifest.get("evidence_path", ""),
        "manifest_path": manifest.get("manifest_path", ""),
        "ledger_path": manifest.get("ledger_path", ""),
        "archive_path": manifest.get("archive_path", ""),
        "signature_state": manifest.get("signature_state", ""),
        "created_at": manifest.get("created_at", ""),
    }


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
