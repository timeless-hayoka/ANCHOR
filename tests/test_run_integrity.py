"""Regression controls for untrusted run telemetry and registry claims."""
import asyncio
import importlib
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def server(monkeypatch, tmp_path):
    monkeypatch.setenv("ANCHOR_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ANCHOR_SIGNING_KEY_PATH", str(tmp_path / "key.pem"))
    return importlib.reload(importlib.import_module("anchor_server"))


def test_imported_label_is_not_execution_evidence(server):
    case = server.case_from_registry({
        "case_id": "claim", "validation_state": "REPRODUCED_REAL",
        "reproduction_status": "REPRODUCED_REAL", "reproduced_real": ["SWC-107"],
    })
    assert case["execution_artifacts"] == []
    assert case["validation_state"] == "POC_EXECUTED_UNPROVEN"
    assert case["reproduction_status"] == "UNVERIFIED"
    assert case["reproduced_real"] == []
    assert case["claimed_validation_state"] == "REPRODUCED_REAL"


def test_live_metrics_require_ground_truth(server):
    run = server.create_run("hunt")
    run.cases["failed"] = {"case_id": "failed", "validation_state": "FAILED"}
    registry = server.build_registry_from_cases(run)
    assert registry["reproduced"] == 0
    assert all(registry[k] is None for k in ("precision", "recall", "f1"))


@pytest.mark.parametrize("value", ["false", "true", 1, [], None])
def test_poc_boolean_is_strict(server, value):
    run = server.create_run("hunt")
    server.RUNS[run.run_id] = run
    with TestClient(server.app) as client:
        response = client.post(f"/runs/{run.run_id}/ingest", headers={"X-Anchor-Ingest-Token": run.ingest_token}, json={
            "type": "poc.result", "payload": {"case_id": "claim", "exploit_verified": value},
        })
    assert response.status_code == 400
    assert run.cases == {}


def test_boolean_true_still_is_not_independent_proof(server):
    run = server.create_run("hunt")
    asyncio.run(run.emit("poc.result", {
        "case_id": "claim", "swc": "SWC-107", "exploit_verified": True,
    }))
    assert run.cases["claim"]["validation_state"] == "POC_EXECUTED_UNPROVEN"
    assert run.cases["claim"]["execution_artifacts"] == []
    asyncio.run(run.emit("case.completed", {
        "case_id": "claim", "validation_state": "REPORT_READY",
    }))
    assert run.cases["claim"]["validation_state"] == "POC_EXECUTED_UNPROVEN"


def test_terminal_run_is_immutable(server):
    run = server.create_run("hunt")
    server.RUNS[run.run_id] = run
    asyncio.run(run.emit("run.completed", {}))
    before = list(run.events)
    with TestClient(server.app) as client:
        response = client.post(f"/runs/{run.run_id}/ingest", headers={"X-Anchor-Ingest-Token": run.ingest_token}, json={
            "type": "case.started", "payload": {"case_id": "late"},
        })
    assert response.status_code == 409
    assert run.events == before
    assert run.cases == {}


@pytest.mark.parametrize("exit_code,preexisting", [(7, True), (0, True), (0, False)])
def test_failed_or_stale_or_unbound_registry_is_not_replayed(server, tmp_path, exit_code, preexisting):
    registry = {"results": [{"case_id": "stale", "validation_state": "REPRODUCED_REAL"}]}
    path = tmp_path / "registry.json"
    if preexisting:
        path.write_text(json.dumps(registry))
    script = tmp_path / "anchor_hunt.py"
    script.write_text(
        "import json\nfrom pathlib import Path\n"
        + ("" if preexisting else f"Path('registry.json').write_text({json.dumps(registry)!r})\n")
        + f"raise SystemExit({exit_code})\n"
    )
    run = server.create_run("hunt", script=str(script), registry=str(path))
    asyncio.run(server.hunt_run(run))
    assert run.status == "failed"
    assert run.registry["reproduced"] == 0
    assert not any(e["type"] == "poc.result" for e in run.events)
    assert run.events[-1]["type"] == "run.failed"


def test_nonzero_exit_discards_live_proof_claims(server, tmp_path):
    script = tmp_path / "anchor_hunt.py"
    script.write_text("raise SystemExit(7)\n")
    run = server.create_run("hunt", script=str(script))
    asyncio.run(server.hunt_run(run))
    assert run.process.returncode == 7
    assert run.status == "failed"
    assert run.events[-1]["payload"]["exit_code"] == 7


def test_fresh_bound_registry_remains_an_unverified_claim(server, tmp_path):
    script = tmp_path / "anchor_hunt.py"
    script.write_text(
        "import json,os\nfrom pathlib import Path\n"
        "p=Path(os.environ['ANCHOR_REGISTRY_PATH']);p.parent.mkdir(parents=True,exist_ok=True)\n"
        "p.write_text(json.dumps({'run_id':os.environ['ANCHOR_RUN_ID'],"
        "'target':os.environ['ANCHOR_TARGET'],'results':[{'case_id':'new',"
        "'validation_state':'REPRODUCED_REAL','swc':'SWC-107'}]}))\n"
    )
    run = server.create_run("hunt", script=str(script), target="local@revision")
    asyncio.run(server.hunt_run(run))
    assert run.status == "done"
    assert run.registry["run_id"] == run.run_id
    assert run.registry["reproduced"] == 0
    assert run.cases["new"]["validation_state"] == "POC_EXECUTED_UNPROVEN"
    assert run.cases["new"]["execution_artifacts"] == []
