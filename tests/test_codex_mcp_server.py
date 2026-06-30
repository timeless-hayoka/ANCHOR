from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


codex_mcp_server = load_module("codex_mcp_server", "codex_mcp_server.py")


def test_repo_status_snapshot_includes_workspace_health():
    snapshot = codex_mcp_server.repo_status()
    assert snapshot["root"].endswith("/ANCHOR")
    assert isinstance(snapshot["top_level_entries"], list)
    assert snapshot["git"]["ok"] in {True, False}
    assert "latest_published_benchmark" in snapshot


def test_work_queue_snapshot_tracks_queue_summary():
    snapshot = codex_mcp_server.work_queue()
    assert snapshot["kind"] == "anchor.work_queue"
    assert snapshot["counts"]["total"] >= 0
    assert "summary" in snapshot


def test_benchmark_latest_snapshot_returns_rendered_summary(monkeypatch):
    current = {
        "id": "run-a",
        "target": "defihacklabs",
        "level": "Phase 3",
        "confidence": "measured",
        "executed_at": "2026-06-29T18:46:05+00:00",
        "publication_tier": "published",
        "results_summary": {"passed": 4, "failed": 1, "timed_out": 0, "detector_signals": 4, "medium_high_target_relevant_findings": 1},
        "source_tool_compare_json": "benchmarks/defihacklabs/source-comparison/runs/run-a/source_tool_compare.json",
    }
    compare = {
        "source_tool": "slither",
        "comparison": {
            "anchor_visible": 4,
            "source_tool_visible": 4,
            "shared_visible": 3,
            "anchor_only": 1,
            "source_only": 1,
        },
    }
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "load_manifest", lambda: [current])
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "find_latest_published_benchmark", lambda entries: current)
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "load_source_tool_compare", lambda entry: compare)
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "render_benchmark_latest", lambda entry: "LATEST")
    snapshot = codex_mcp_server.benchmark_latest()
    assert snapshot["status"] == "ok"
    assert snapshot["rendered"] == "LATEST"
    assert snapshot["source_tool_compare"]["source_tool"] == "slither"


def test_compare_source_snapshot_returns_rendered_summary(monkeypatch):
    entries = [{"id": "run-a", "target": "defihacklabs", "source_tool_compare_json": "benchmarks/defihacklabs/source-comparison/runs/run-a/source_tool_compare.json"}]
    compare = {
        "source_tool": "slither",
        "comparison": {
            "anchor_visible": 4,
            "source_tool_visible": 4,
            "shared_visible": 3,
            "anchor_only": 1,
            "source_only": 1,
        },
    }
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "load_manifest", lambda: entries)
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "find_entry", lambda entries_arg, run_id: entries_arg[0])
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "load_source_tool_compare", lambda entry: compare)
    monkeypatch.setattr(codex_mcp_server.anchor_cli, "render_benchmark_source_tool_compare", lambda payload: "COMPARE")
    snapshot = codex_mcp_server.benchmark_compare_source("run-a")
    assert snapshot["status"] == "ok"
    assert snapshot["rendered"] == "COMPARE"
    assert snapshot["comparison"]["source_tool"] == "slither"


def test_decode_stdio_line_ignores_blank_lines():
    assert codex_mcp_server._decode_stdio_line("\n") is None
    assert codex_mcp_server._decode_stdio_line("   \n") is None
