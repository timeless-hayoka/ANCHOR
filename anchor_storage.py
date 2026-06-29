from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def evidence_dir(root: str | Path | None = None) -> Path:
    base = Path(root) if root is not None else ROOT
    return base / "benchmarks" / "evidence"


def storage_manifest_path(root: str | Path | None = None) -> Path:
    base = Path(root) if root is not None else ROOT
    return base / "storage.json"


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_storage_manifest(
    *,
    benchmark_id: str,
    run_id: str,
    target: str,
    stage: str,
    status: str,
    artifact_path: str,
    evidence_path: str,
    manifest_path: str,
    ledger_path: str,
    archive_path: str,
) -> dict[str, Any]:
    return {
        "benchmark_id": benchmark_id,
        "run_id": run_id,
        "target": target,
        "stage": stage,
        "status": status,
        "artifact_path": artifact_path,
        "evidence_path": evidence_path,
        "manifest_path": manifest_path,
        "ledger_path": ledger_path,
        "archive_path": archive_path,
        "signature_state": "pending",
        "published_at": None,
    }


def storage_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_id": manifest.get("benchmark_id"),
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "signature_state": manifest.get("signature_state", "pending"),
        "manifest_path": manifest.get("manifest_path"),
    }
