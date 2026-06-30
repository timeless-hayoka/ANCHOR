from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from bugbot.analysis import (
    AnalysisConfig,
    AnalysisExecutionTrace,
    AnalysisRunResult,
    AnalysisStageResult,
    run_target_analysis,
)
from bugbot.analysis_record import (
    FINAL_STATUS_BLOCKED,
    FINAL_STATUS_FAILED,
    FINAL_STATUS_PARTIAL,
    FINAL_STATUS_PASS,
    build_analysis_record,
    derive_final_status,
)
from bugbot.scope import (
    ANALYSIS,
    IDENTITY_LOCAL_FIXTURE_UNPINNED,
    IDENTITY_VERIFIED_REPO,
    REVIEWER_DECISION_AUTHORIZED,
    ScopeGrant,
)
from knowledge.pipeline import KnowledgePipeline
from evidence_schema import is_canonical_evidence

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _grant(**overrides) -> ScopeGrant:
    base = {
        "schema_version": "1.0",
        "target_id": "dvd-local-lab",
        "target_ref": "abc123def4567890abcdef1234567890abcdef12",
        "scope_policy_url": "https://example.com/security/scope",
        "permitted_actions": (ANALYSIS,),
        "prohibited_actions": ("mainnet-exploit",),
        "disclosure_channel": "local-lab-only",
        "evidence_url": "https://example.com/evidence/dvd-local-lab",
        "evidence_path": str(FIXTURES / "scope_evidence.md"),
        "reviewer_decision": REVIEWER_DECISION_AUTHORIZED,
        "reviewed_at": datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
        "identity_status": IDENTITY_LOCAL_FIXTURE_UNPINNED,
        "expires_at": datetime(2027, 6, 30, 12, 0, tzinfo=timezone.utc),
        "confirmation_source": str(FIXTURES / "scope_confirmation_valid.md"),
    }
    base.update(overrides)
    return ScopeGrant(**base)


def test_derive_final_status_matrix() -> None:
    pass_result = AnalysisRunResult(success=True, workspace=Path("/tmp/lab"))
    assert derive_final_status(pass_result) == FINAL_STATUS_PASS

    blocked = AnalysisRunResult(
        success=False,
        workspace=Path("/tmp/lab"),
        blocked=True,
        stages=[AnalysisStageResult("identity", False, "blocked")],
    )
    assert derive_final_status(blocked) == FINAL_STATUS_BLOCKED

    failed = AnalysisRunResult(
        success=False,
        workspace=Path("/tmp/lab"),
        stages=[AnalysisStageResult("clone", False, "clone failed")],
    )
    assert derive_final_status(failed) == FINAL_STATUS_FAILED

    partial = AnalysisRunResult(
        success=False,
        workspace=Path("/tmp/lab"),
        stages=[
            AnalysisStageResult("identity", True, "verified"),
            AnalysisStageResult("inspect", False, "empty"),
        ],
    )
    assert derive_final_status(partial) == FINAL_STATUS_PARTIAL


def test_build_analysis_record_includes_required_fields(tmp_path: Path) -> None:
    anchor = tmp_path / "anchor"
    scope_dir = anchor / "scope"
    scope_dir.mkdir(parents=True)
    (scope_dir / "active_grant.json").write_text("{}", encoding="utf-8")
    workspace = tmp_path / "lab"
    workspace.mkdir()
    started = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    completed = datetime(2026, 6, 30, 12, 1, tzinfo=timezone.utc)
    result = AnalysisRunResult(
        success=True,
        workspace=workspace,
        identity_status=IDENTITY_LOCAL_FIXTURE_UNPINNED,
        started_at=started,
        completed_at=completed,
        stages=[
            AnalysisStageResult(
                "clone",
                True,
                "using existing non-git workspace",
                started_at=started,
                finished_at=completed,
            ),
            AnalysisStageResult(
                "identity",
                True,
                "identity_status=local_fixture_unpinned",
                started_at=started,
                finished_at=completed,
            ),
        ],
    )
    config = AnalysisConfig(
        target_id="dvd-local-lab",
        target_ref="abc123",
        grant=_grant(),
        workspace=workspace,
        anchor_root=anchor,
        archive=False,
    )
    record = build_analysis_record(config, result, AnalysisExecutionTrace())
    assert record["record_type"] == "analysis_run"
    assert record["final_status"] == FINAL_STATUS_PASS
    assert record["scope_authorization"]["reviewer_decision"] == REVIEWER_DECISION_AUTHORIZED
    assert record["identity"]["identity_status"] == IDENTITY_LOCAL_FIXTURE_UNPINNED
    assert record["execution_environment"]["workspace"] == str(workspace.resolve())
    assert "tool_versions" in record
    assert isinstance(record["stages"], list)


def test_run_target_analysis_archives_record(tmp_path: Path) -> None:
    anchor = tmp_path / "anchor"
    knowledge = anchor / "knowledge"
    workspace = tmp_path / "lab"
    workspace.mkdir()
    (workspace / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "Token.sol").write_text("// sol", encoding="utf-8")

    result = run_target_analysis(
        AnalysisConfig(
            target_id="dvd-local-lab",
            target_ref="deadbeef",
            grant=_grant(),
            workspace=workspace,
            anchor_root=anchor,
        )
    )

    assert result.success is True
    assert result.archive is not None
    assert result.archive.success is True
    assert result.archive.path is not None
    assert result.archive.path.parent == knowledge / "analysis"
    payload = json.loads(result.archive.path.read_text(encoding="utf-8"))
    assert payload["final_status"] == FINAL_STATUS_PASS
    assert payload["target"]["target_id"] == "dvd-local-lab"
    assert payload["artifact_paths"]["archive_record"] == str(result.archive.path)
    assert is_canonical_evidence(payload)
    assert payload["kind"] == "hunt_analysis"
    assert payload["status"] == "published"


def test_write_analysis_run_via_pipeline(tmp_path: Path) -> None:
    pipeline = KnowledgePipeline(tmp_path)
    result = pipeline.archive_analysis_run(
        {
            "record_type": "analysis_run",
            "final_status": FINAL_STATUS_BLOCKED,
            "target": {"target_id": "x"},
        }
    )
    assert result.success is True
    assert result.path is not None
    assert result.path.parent.name == "analysis"
    payload = json.loads(result.path.read_text(encoding="utf-8"))
    assert payload["final_status"] == FINAL_STATUS_BLOCKED
    assert payload["artifact_paths"]["archive_record"] == str(result.path)
    assert is_canonical_evidence(payload)
    assert payload["status"] == "rejected"
