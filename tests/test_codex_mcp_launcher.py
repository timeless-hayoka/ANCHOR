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


launcher = load_module("codex_mcp_launcher", "scripts/codex_mcp_launcher.py")


def test_registration_payload_points_at_repo_server():
    payload = launcher.registration_payload()
    server = payload["mcpServers"]["anchor-codex"]
    assert server["command"]
    assert server["args"] == [str(ROOT / "codex_mcp_server.py")]
    assert server["cwd"] == str(ROOT)


def test_print_registration_emits_json(capsys):
    rc = launcher.print_registration()
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["mcpServers"]["anchor-codex"]["args"] == [str(ROOT / "codex_mcp_server.py")]
