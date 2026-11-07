import asyncio
import importlib
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from anchor_execution import execution_env, run_bounded
from anchor_sandbox import sandbox_command


@pytest.fixture
def server(monkeypatch, tmp_path):
    monkeypatch.setenv("ANCHOR_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ANCHOR_SIGNING_KEY_PATH", str(tmp_path / "key.pem"))
    return importlib.reload(importlib.import_module("anchor_server"))


def test_origin_rejected_before_mutation(server):
    with TestClient(server.app) as client:
        assert client.post("/runs", json={"mode": "demo"}, headers={"Origin": "https://untrusted.example"}).status_code == 403
        preflight = client.options("/runs", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in preflight.headers
    assert server.RUNS == {}


def test_body_limit_rejected_without_content_length(server):
    with TestClient(server.app) as client:
        response = client.post("/runs", content=iter([b"x" * 600000, b"x" * 600000]))
        assert response.status_code == 413
    assert server.RUNS == {}


def test_producer_authentication_and_lifecycle_authority(server):
    run = server.create_run("hunt")
    server.RUNS[run.run_id] = run
    with TestClient(server.app) as client:
        url = f"/runs/{run.run_id}/ingest"
        event = {"type": "case.started", "payload": {"case_id": "new"}}
        assert client.post(url, json=event).status_code == 403
        assert not run.events
        headers = {"X-Anchor-Ingest-Token": run.ingest_token}
        assert client.post(url, json={"type": "run.completed", "payload": {}}, headers=headers).status_code == 400
        assert not run.done.is_set()
        assert client.post(url, json=event, headers=headers).status_code == 200


def test_hunt_script_basename_does_not_authorize_other_path(server, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    script = other / "anchor_hunt.py"
    script.write_text("raise AssertionError('must not run')")
    run = server.create_run("hunt", script=str(script))
    asyncio.run(server.hunt_run(run))
    assert run.status == "failed"
    assert run.process is None


def test_helpers_do_not_inherit_secrets_or_python_hooks(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "audit-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "audit-sentinel")
    monkeypatch.setenv("PYTHONPATH", "/untrusted")
    env = execution_env()
    assert not {"GITHUB_TOKEN", "OPENAI_API_KEY", "PYTHONPATH"} & env.keys()
    result = run_bounded([sys.executable, "-c", "import os; print(os.getenv('GITHUB_TOKEN'))"], timeout=3)
    assert result.stdout.strip() == "None"


def test_command_deadline_and_output_limit():
    with pytest.raises(subprocess.TimeoutExpired):
        run_bounded([sys.executable, "-c", "import time; time.sleep(10)"], timeout=1)
    with pytest.raises(ValueError, match="output limit"):
        run_bounded([sys.executable, "-c", "import sys; sys.stdout.write('x' * 2000000)"], timeout=3)


def test_sandbox_failure_never_runs_target_on_host(tmp_path):
    if not Path("/usr/bin/bwrap").exists():
        pytest.skip("bubblewrap is unavailable")
    # Either the namespace cannot start, or this path is hidden inside it.
    sentinel = tmp_path / "host-only.txt"
    work = tmp_path / "work"
    work.mkdir()
    cmd = sandbox_command(["/usr/bin/python3", "-c", f"open({str(sentinel)!r}, 'w').write('bad')"], work)
    result = run_bounded(cmd, timeout=3)
    assert result.returncode != 0
    assert not sentinel.exists()


def test_source_context_cannot_follow_external_symlink(tmp_path):
    from anchor_sarif.pipeline import SARIFProcessingPipeline
    from anchor_sarif.parser import Finding
    source = tmp_path / "src"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("sentinel")
    (source / "link.sol").symlink_to(outside)
    pipeline = SARIFProcessingPipeline(db_path=tmp_path / "findings.db", source_root=source)
    assert pipeline._get_context(Finding("tool", "rule", "warning", "m", "link.sol", 1)) == ""
    assert pipeline._get_context(Finding("tool", "rule", "warning", "m", str(outside), 1)) == ""


def test_identity_rejects_modified_untracked_and_ignored_files(tmp_path):
    from datetime import datetime, timezone
    from bugbot.scope import ScopeGrant, IDENTITY_VERIFIED_REPO
    from bugbot.target_identity import verify_target_identity
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], text=True, capture_output=True, check=True).stdout.strip()
    git("init")
    git("config", "user.email", "audit@example.invalid")
    git("config", "user.name", "Audit")
    source = tmp_path / "Vault.sol"
    source.write_text("original")
    (tmp_path / ".gitignore").write_text("ignored.sol\n")
    git("add", ".")
    git("commit", "-m", "fixture")
    git("remote", "add", "origin", "https://github.com/audit/fixture")
    grant = ScopeGrant("1.0", "audit/fixture", git("rev-parse", "HEAD"), "local", ("analysis",), (), "local", "local", "local", "AUTHORIZED", datetime.now(timezone.utc), identity_status=IDENTITY_VERIFIED_REPO, target_repo_url="https://github.com/audit/fixture")
    assert verify_target_identity(tmp_path, grant).verified
    source.write_text("modified")
    assert not verify_target_identity(tmp_path, grant).verified
    git("restore", "Vault.sol")
    for name in ("untracked.sol", "ignored.sol"):
        path = tmp_path / name
        path.write_text("unapproved")
        assert not verify_target_identity(tmp_path, grant).verified
        path.unlink()
