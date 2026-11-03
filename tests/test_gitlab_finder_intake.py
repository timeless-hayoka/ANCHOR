"""Security regressions for GitLab's deliberately scope-neutral Finder intake."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "gitlab_finder_intake", Path(__file__).resolve().parents[1] / "scripts/gitlab_finder_intake.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PUBLIC = {
    "path_with_namespace": "example/solidity-sandbox",
    "web_url": "https://gitlab.com/example/solidity-sandbox",
    "visibility": "public", "archived": False, "empty_repo": False,
    "description": "Simple smart contract educational codebase",
    "last_activity_at": "2026-10-29T12:00:00Z",
}


def test_public_repository_is_metadata_only_not_authorized():
    data = mod.normalize_projects({"data": [PUBLIC]})
    assert len(data["candidates"]) == 1
    c = data["candidates"][0]
    assert c["host"] == "gitlab.com"
    assert c["scan_status"] == "metadata_only"
    assert c["scope_status"] == "UNCONFIRMED"
    assert c["authorization"] == "NOT_GRANTED"
    assert c["trinity_state"] == "NOT_CREATED"
    assert data["eligible_for_active_testing"] is False
    assert data["finder_handoff"] == "NOT_AUTHORIZED"


def test_private_archived_empty_duplicate_and_wrong_host_rejected():
    result = mod.normalize_projects([
        PUBLIC,
        {**PUBLIC, "path_with_namespace": "example/hidden", "web_url": "https://gitlab.com/example/hidden", "visibility": "private"},
        {**PUBLIC, "path_with_namespace": "example/old", "web_url": "https://gitlab.com/example/old", "archived": True},
        {**PUBLIC, "path_with_namespace": "example/empty", "web_url": "https://gitlab.com/example/empty", "empty_repo": True},
        {**PUBLIC, "path_with_namespace": "example/not-gitlab", "web_url": "https://evil.example/example/not-gitlab"},
        PUBLIC,
    ])
    assert len(result["candidates"]) == 1
    assert result["rejected_counts"] == {
        "not_public": 1,
        "archived_or_empty": 2,
        "host_or_identity_mismatch": 1,
        "duplicate": 1,
    }


def test_path_mismatch_and_malformed_payload_do_not_pass():
    data = mod.normalize_projects([{**PUBLIC, "path_with_namespace": "example/other"}])
    assert data["candidates"] == []
    with pytest.raises(ValueError):
        mod.normalize_projects({"projects": [PUBLIC]})
    with pytest.raises(ValueError):
        mod.normalize_projects([PUBLIC] * 501)


def test_cli_preserves_existing_artifact_and_records_input_hash(tmp_path, capsys):
    incoming = tmp_path / "gitlab.json"
    output = tmp_path / "intake.json"
    incoming.write_text(json.dumps({"data": [PUBLIC]}), encoding="utf-8")
    args = ["--input", str(incoming), "--output", str(output)]
    assert mod.main(args) == 0
    original = output.read_bytes()
    assert json.loads(original)["input_sha256"]
    assert mod.main(args) == 2
    assert output.read_bytes() == original


def test_cli_rejects_malformed_json_without_output(tmp_path):
    incoming = tmp_path / "invalid.json"
    output = tmp_path / "intake.json"
    incoming.write_text("{", encoding="utf-8")
    assert mod.main(["--input", str(incoming), "--output", str(output)]) == 2
    assert not output.exists()
