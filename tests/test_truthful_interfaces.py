import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def server(monkeypatch, tmp_path):
    monkeypatch.setenv("ANCHOR_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ANCHOR_SIGNING_KEY_PATH", str(tmp_path / "key.pem"))
    return importlib.reload(importlib.import_module("anchor_server"))


@pytest.mark.parametrize("body", [{}, {"mode": "typo"}, [], {"mode": 1}])
def test_runs_require_explicit_valid_mode(server, body):
    with TestClient(server.app) as client:
        assert client.post("/runs", json=body).status_code == 400
    assert not server.RUNS


def test_no_fixture_case_fallback_or_fake_authentication(server):
    with TestClient(server.app) as client:
        assert client.get("/cases/TinyReentrancy").status_code == 404
        assert client.get("/api/anchor/session").json()["authenticated"] is False
        chat = client.post("/api/trinity/chat", json={"message": "hello"}).json()
        assert chat["mode"] == "help_only"
        assert chat["model_connected"] is False
        assert client.post("/api/trinity/chat", json=["bad"]).status_code == 400


def test_demo_records_and_signatures_are_labeled(server):
    assert server.specimen_registry()["provenance"] == "DEMO_FIXTURE"
    assert all(row["provenance"] == "DEMO_FIXTURE" for row in server.specimen_registry()["results"])
    assert server.sign_bundle({"validation_state": "REPRODUCED_REAL"})["attestation"] == "CONTENT_SIGNATURE_ONLY"


@pytest.mark.parametrize("command", ["cluster", "tune", "visualize"])
def test_unimplemented_commands_do_not_claim_success(command, tmp_path):
    import anchor_cli
    args = anchor_cli.create_parser().parse_args(["sarif", command])
    assert getattr(anchor_cli, f"cmd_sarif_{command}")(args) == 2


def test_default_processing_needs_no_optional_ml(tmp_path):
    from anchor_sarif.pipeline import SARIFProcessingPipeline
    pipeline = SARIFProcessingPipeline(db_path=tmp_path / "findings.db")
    assert pipeline.clusterer is None


def test_module_research_and_visualize_dispatch(tmp_path, capsys):
    from anchor_sarif.cli import main
    source = tmp_path / "slither.sarif"
    source.write_text('{"version":"2.1.0","runs":[{"tool":{"driver":{"name":"slither"}},"results":[]}]}')
    assert main(["research", str(source), "--db", str(tmp_path / "f.db")]) == 0
    assert main(["visualize", "--db", str(tmp_path / "f.db")]) == 2
