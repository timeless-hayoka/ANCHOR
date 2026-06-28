from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCRIPT_REGISTRY_PATH = ROOT / "scripts" / "registry.json"
DEFAULT_ALLOWLIST = {
    name.strip()
    for name in os.getenv("ANCHOR_ALLOWED_HUNT_SCRIPTS", "trinity_hunt_v4_2_fixed.py,anchor_hunt.py").split(",")
    if name.strip()
}


def load_script_registry(path: Path | None = None) -> dict[str, Any]:
    candidate = path or SCRIPT_REGISTRY_PATH
    if not candidate.exists():
        return {
            "schema_version": "1.0",
            "kind": "anchor.script_registry",
            "registry_path": str(candidate),
            "scripts": [],
        }
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        payload = {"scripts": payload if isinstance(payload, list) else []}
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("kind", "anchor.script_registry")
    payload.setdefault("registry_path", str(candidate))
    payload.setdefault("scripts", [])
    return payload


def registry_scripts(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = registry or load_script_registry()
    scripts = payload.get("scripts", [])
    return [item for item in scripts if isinstance(item, dict)]


def registry_summary(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = registry or load_script_registry()
    scripts = registry_scripts(payload)
    allowed = [item for item in scripts if item.get("allowed", True)]
    return {
        "schema_version": payload.get("schema_version", "1.0"),
        "registry_path": payload.get("registry_path", str(SCRIPT_REGISTRY_PATH)),
        "script_count": len(scripts),
        "allowed_count": len(allowed),
        "names": [str(item.get("name") or item.get("path") or "") for item in scripts if (item.get("name") or item.get("path"))],
        "allowed_names": [str(item.get("name") or item.get("path") or "") for item in allowed if (item.get("name") or item.get("path"))],
    }


def allowed_script_names(registry: dict[str, Any] | None = None) -> set[str]:
    names = set(DEFAULT_ALLOWLIST)
    for item in registry_scripts(registry):
        if item.get("allowed", True):
            name = str(item.get("name") or item.get("path") or "").strip()
            if name:
                names.add(Path(name).name)
    return names
