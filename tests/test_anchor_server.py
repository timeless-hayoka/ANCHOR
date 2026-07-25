from __future__ import annotations

import importlib
import json
import stat
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def load_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    key_path = tmp_path / "anchor_signing_key.pem"
    monkeypatch.setenv("ANCHOR_SIGNING_KEY_PATH", str(key_path))
    monkeypatch.setenv("ANCHOR_PROJECT_ROOT", "/home/crexs/infj_bot")
    module = importlib.import_module("anchor_server")
    return importlib.reload(module)


def parse_sse_events(lines):
    events = []
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode()
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    return events


def test_anchor_server_demo_run_streams_and_signs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    server = load_server(monkeypatch, tmp_path)
    assert stat.S_IMODE(Path(server.SIGNING_KEY_PATH).stat().st_mode) == 0o600

    with TestClient(server.app) as client:
        root = client.get("/api/service")


def test_anchor_snapshot_prefers_published_benchmark(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    server = load_server(monkeypatch, tmp_path)
    manifest_path = tmp_path / "benchmarks.json"
    manifest_path.write_text(json.dumps({
        "benchmarks": [
            {
                "id": "dev-run",
                "target": "damn-vulnerable-defi",
                "title": "Development run",
                "status": "scaffold",
                "publication_tier": "development",
                "executed_at": "2026-06-27T09:00:00+00:00",
            },
            {
                "id": "pub-run",
                "target": "damn-vulnerable-defi",
                "title": "Published run",
                "status": "published",
                "publication_tier": "published",
                "executed_at": "2026-06-26T09:00:00+00:00",
                "results_summary": {"passed": 15, "failed": 2, "timed_out": 1, "detector_signals": 58, "medium_high_target_relevant_findings": 58},
            },
        ]
    }))
    server.BENCHMARK_MANIFEST = manifest_path

    with TestClient(server.app) as client:
        snapshot = client.get("/api/anchor/snapshot?limit=5")
        assert snapshot.status_code == 200
        snap = snapshot.json()
        assert snap["benchmark_overview"]["benchmark_id"] == "pub-run"
        assert snap["benchmark_overview"]["regression_report"] == ""
        assert snap["research_loop"]["benchmark_id"] == "pub-run"
        assert snap["research_loop"]["queue_depth"] >= 1
        assert snap["work_queue"]["counts"]["active"] == 1
        assert snap["work_queue"]["top_item"]["id"] == "A-001"
        assert snap["benchmarks"][0]["id"] == "pub-run"
        assert isinstance(snap["evidence_summary"]["sources"], dict)
        assert "Benchmarks" in snap["evidence_summary"]["sources"]
        assert isinstance(snap["evidence_summary"]["latest"], list)
        service = client.get("/api/service")
        assert service.status_code == 200
        assert service.json()["service"] == "anchor"

        pubkey = client.get("/pubkey")
        assert pubkey.status_code == 200
        assert pubkey.json()["algorithm"] == "ed25519"

        scripts = client.get("/api/trinity/scripts")
        assert scripts.status_code == 200
        assert scripts.json()["summary"]["script_count"] >= 1

        snapshot = client.get("/api/anchor/snapshot?limit=5")
        assert snapshot.status_code == 200
        snap = snapshot.json()
        assert "benchmark_overview" in snap
        assert "research_loop" in snap
        assert "script_registry" in snap
        assert "scabench" in snap
        assert "score" in snap["scabench"]

        started = client.post("/runs", json={"mode": "demo"})
        assert started.status_code == 200
        run_id = started.json()["run_id"]

        with client.stream("GET", f"/runs/{run_id}/events") as stream:
            events = parse_sse_events(stream.iter_lines())

        types = [event["type"] for event in events]
        assert "run.started" in types
        assert "case.started" in types
        assert "stage.started" in types
        assert "finding.detected" in types
        assert "finding.correlated" in types
        assert "poc.result" in types
        assert "case.completed" in types
        assert "run.completed" in types
        assert types.index("run.started") < types.index("case.started") < types.index("finding.detected") < types.index("finding.correlated") < types.index("poc.result") < types.index("case.completed") < types.index("run.completed")

        evidence = client.post("/evidence/sign", json={"bundle": {"schema_version": "1.0", "kind": "anchor.evidence_bundle", "case_id": "demo"}})
        assert evidence.status_code == 200
        signed = evidence.json()["signed_bundle"]
        assert signed["signature"]["status"] == "SIGNED"
        assert signed["integrity"]["algorithm"] == "SHA-256"
        assert len(signed["integrity"]["digest"]) == 64
        assert signed["public_key"] == pubkey.json()["public_key"]


def test_anchor_server_replays_after_cursor_and_ingests_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    server = load_server(monkeypatch, tmp_path)

    with TestClient(server.app) as client:
        started = client.post("/runs", json={"mode": "demo"})
        run_id = started.json()["run_id"]

        with client.stream("GET", f"/runs/{run_id}/events") as stream:
            all_events = parse_sse_events(stream.iter_lines())

        assert len(all_events) >= 2
        first_event_id = all_events[0]["event_id"]
        second_event_id = all_events[1]["event_id"]

        with client.stream("GET", f"/runs/{run_id}/events?after={first_event_id}") as stream:
            replayed = parse_sse_events(stream.iter_lines())

        assert replayed
        assert replayed[0]["event_id"] == second_event_id
        assert replayed[0]["event_id"] != first_event_id

        ingest = client.post(
            f"/runs/{run_id}/ingest",
            json={"type": "case.started", "payload": {"case_id": "case_live", "contract": "Demo", "expected": ["SWC-107"]}},
        )
        assert ingest.status_code == 200

        case = client.get("/cases/case_live")
        assert case.status_code == 200
        assert case.json()["case_id"] == "case_live"


def test_anchor_server_exposes_latest_github_discovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    server = load_server(monkeypatch, tmp_path)
    discovery_root = tmp_path / "discoveries" / "github"
    left = discovery_root / "2026-07-24t10-00-00-000000-00-00"
    right = discovery_root / "2026-07-25t10-00-00-000000-00-00"
    right.mkdir(parents=True)
    left.mkdir()
    left_bundle = {
        "generated_at": "2026-07-24T10:00:00+00:00",
        "profile": "general",
        "profile_label": "General discovery",
        "queries": ["general"],
        "query_terms": ["general"],
        "summary": {"selected": 1, "total_candidates": 1, "join": 0, "watch": 0, "skip": 1},
        "candidates": [
            {"full_name": "owner/general", "priority_score": 40, "recommendation": "skip", "likely_surface": ["docs"], "security_signals": []}
        ],
    }
    right_bundle = {
        "generated_at": "2026-07-25T10:00:00+00:00",
        "profile": "upgrade",
        "profile_label": "Upgradeability",
        "queries": ["upgrade"],
        "query_terms": ["upgrade"],
        "summary": {"selected": 2, "total_candidates": 2, "join": 0, "watch": 2, "skip": 0},
        "candidates": [
            {"full_name": "owner/shared", "priority_score": 66, "recommendation": "watch", "likely_surface": ["upgradeability"], "security_signals": ["audit/advisory language present"]},
            {"full_name": "owner/upgrade-only", "priority_score": 64, "recommendation": "watch", "likely_surface": ["upgradeability", "access control"], "security_signals": []},
        ],
    }
    (left / "bundle.json").write_text(json.dumps(left_bundle), encoding="utf-8")
    (right / "bundle.json").write_text(json.dumps(right_bundle), encoding="utf-8")
    monkeypatch.setattr(server, "DISCOVERY_ROOT", discovery_root)

    with TestClient(server.app) as client:
        discovery = client.get("/api/github/discovery")
        assert discovery.status_code == 200
        body = discovery.json()
        assert body["kind"] == "anchor.github_discovery.latest"
        assert len(body["runs"]) == 2
        assert body["comparison"]["delta"]["watch"] == 2
        snapshot = client.get("/api/anchor/snapshot?limit=5")
        assert snapshot.status_code == 200
        snap = snapshot.json()
        assert "github_discovery" in snap
        assert snap["github_discovery"]["comparison"]["delta"]["watch"] == 2


def test_knowledge_api_list_show_and_search(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    server = load_server(monkeypatch, tmp_path)

    with TestClient(server.app) as client:
        listing = client.get("/api/knowledge")
        assert listing.status_code == 200
        body = listing.json()
        assert body["version"] == 1
        slugs = {row["slug"] for row in body["topics"]}
        assert "sarif" in slugs

        doc = client.get("/api/knowledge/sarif")
        assert doc.status_code == 200
        assert doc.json()["topic"]["slug"] == "sarif"
        assert doc.json()["content"]

        search = client.get("/api/knowledge/search", params={"q": "confidence", "limit": 3})
        assert search.status_code == 200
        assert search.json()["hits"]

        missing = client.get("/api/knowledge/not-a-topic")
        assert missing.status_code == 404
