from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "scripts" / "registry.json"

DEFAULT_REGISTRY = {
    "registry_path": str(REGISTRY_PATH),
    "scripts": [
        {
            "name": "trinity_hunt_v4_2_fixed.py",
            "allowed": True,
            "description": "Default ANCHOR hunt driver",
        },
        {
            "name": "trinity_hunt.py",
            "allowed": True,
            "description": "Legacy hunt driver alias",
        },
    ],
}


def load_script_registry() -> dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("registry_path", str(REGISTRY_PATH))
                payload.setdefault("scripts", [])
                return payload
        except Exception:
            pass
    return dict(DEFAULT_REGISTRY)


def allowed_script_names(registry: dict[str, Any] | None = None) -> list[str]:
    payload = registry or load_script_registry()
    scripts = payload.get("scripts") or []
    names: list[str] = []
    for item in scripts:
        if not isinstance(item, dict):
            continue
        if item.get("allowed", True) and item.get("name"):
            names.append(str(item["name"]))
    if not names:
        names = [str(item["name"]) for item in DEFAULT_REGISTRY["scripts"]]
    return names


def registry_summary(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = registry or load_script_registry()
    scripts = payload.get("scripts") or []
    script_names = [str(item.get("name")) for item in scripts if isinstance(item, dict) and item.get("name")]
    allowed = allowed_script_names(payload)
    return {
        "registry_path": payload.get("registry_path", str(REGISTRY_PATH)),
        "script_count": len(script_names) or len(DEFAULT_REGISTRY["scripts"]),
        "allowed_count": len(allowed),
        "scripts": script_names or [item["name"] for item in DEFAULT_REGISTRY["scripts"]],
    }
