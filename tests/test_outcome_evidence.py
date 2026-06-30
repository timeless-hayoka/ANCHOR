from __future__ import annotations

import json
from pathlib import Path

import anchor_cli
from outcome_evidence import (
    collect_evidence_records,
    discover_benchmark_evidence,
    discover_bugbot_training_evidence,
    discover_hunt_analysis_evidence,
    normalize_benchmark_evidence,
    normalize_bugbot_training_evidence,
    normalize_hunt_analysis_evidence,
    render_evidence_insights,
)
from evidence_schema import build_bugbot_training_record, is_canonical_evidence


def test_normalize_bugbot_training_evidence():
    payload = {
        "runner": "bugbot",
        "scenario_pack": "v1",
        "timestamp": "2026-06-30T05:38:57+00:00",
        "total": 1,
        "passed": 1,
        "failed": 0,
        "proofs": [{"id": "uups-initializer-takeover", "result": "PASS", "score": 92}],
    }
    record = normalize_bugbot_training_evidence(
        path=Path("/tmp/ANCHOR/outcomes/training/bugbot-scenarios-test.json"),
        payload=payload,
        anchor_root=Path("/tmp/ANCHOR"),
    )
    assert record["kind"] == "bugbot_training"
    assert record["status"] == "proof_gate_passed"
    assert record["metrics"]["passed"] == 1


def test_normalize_hunt_analysis_evidence():
    payload = {
        "record_type": "analysis_run",
        "analysis_id": "analysis-run-test",
        "completed_at": "2026-06-30T12:00:00+00:00",
        "final_status": "PASS",
        "target": {"target_id": "dvd-local-lab"},
        "stages": [
            {"stage": "identity", "outcome": "PASS"},
            {"stage": "inspect", "outcome": "FAIL"},
        ],
    }
    record = normalize_hunt_analysis_evidence(
        path=Path("/tmp/ANCHOR/knowledge/analysis/analysis-run-test.json"),
        payload=payload,
        anchor_root=Path("/tmp/ANCHOR"),
    )
    assert record["kind"] == "hunt_analysis"
    assert record["target"] == "dvd-local-lab"
    assert record["metrics"]["passed"] == 1
    assert record["metrics"]["failed"] == 1


def test_discover_bugbot_training_evidence(tmp_path):
    training_dir = tmp_path / "outcomes" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "bugbot-scenarios-a.json").write_text(
        json.dumps(
            {
                "runner": "bugbot",
                "scenario_pack": "v1",
                "timestamp": "2026-06-30T05:00:00+00:00",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "proofs": [],
            }
        ),
        encoding="utf-8",
    )
    rows = discover_bugbot_training_evidence(anchor_root=tmp_path, limit=5)
    assert len(rows) == 1
    assert rows[0]["kind"] == "bugbot_training"


def test_discover_hunt_analysis_evidence(tmp_path):
    analysis_dir = tmp_path / "knowledge" / "analysis"
    analysis_dir.mkdir(parents=True)
    (analysis_dir / "analysis-run-test.json").write_text(
        json.dumps(
            {
                "record_type": "analysis_run",
                "analysis_id": "analysis-run-test",
                "completed_at": "2026-06-30T12:00:00+00:00",
                "final_status": "PASS",
                "target": {"target_id": "enzyme-lab"},
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    rows = discover_hunt_analysis_evidence(anchor_root=tmp_path, limit=5)
    assert len(rows) == 1
    assert rows[0]["target"] == "enzyme-lab"


def test_collect_evidence_records_merges_sources(tmp_path):
    training_dir = tmp_path / "outcomes" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "bugbot-scenarios-a.json").write_text(
        json.dumps(
            {
                "runner": "bugbot",
                "scenario_pack": "v1",
                "timestamp": "2026-06-30T06:00:00+00:00",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "proofs": [],
            }
        ),
        encoding="utf-8",
    )
    manifest = [
        {
            "id": "dvd-phase1",
            "target": "damn-vulnerable-defi",
            "executed_at": "2026-06-29T18:00:00+00:00",
            "status": "complete",
            "artifact_json": "benchmarks/dvd/benchmark.json",
            "results_summary": {"passed": 2, "failed": 1, "timed_out": 0, "skipped": 0},
        }
    ]
    run_dir = tmp_path / "benchmarks" / "dvd"
    run_dir.mkdir(parents=True)
    (run_dir / "benchmark.json").write_text(
        json.dumps({"run_id": "dvd-phase1", "results_summary": manifest[0]["results_summary"]}),
        encoding="utf-8",
    )
    rows = collect_evidence_records(
        anchor_root=tmp_path,
        manifest_entries=manifest,
        limit=10,
    )
    kinds = {row["kind"] for row in rows}
    assert "bugbot_training" in kinds
    assert "benchmark" in kinds


def test_render_outcome_insights_includes_evidence_section():
    rendered = anchor_cli.render_outcome_insights(
        [],
        evidence=[
            {
                "kind": "bugbot_training",
                "timestamp": "2026-06-30T06:00:00+00:00",
                "target": "bugbot-scenario-pack/v1",
                "label": "BugBot v1: 1/1 proofs passed",
                "metrics": {"total": 1, "passed": 1, "failed": 0, "proofs": []},
            }
        ],
        top_n=3,
    )
    assert "Evidence artifacts" in rendered
    assert "bugbot_training: 1" in rendered
    assert "BugBot training (latest)" in rendered


def test_cmd_outcome_insights_collects_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(anchor_cli, "ROOT", tmp_path)
    training_dir = tmp_path / "outcomes" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "bugbot-scenarios-a.json").write_text(
        json.dumps(
            {
                "runner": "bugbot",
                "scenario_pack": "v1",
                "timestamp": "2026-06-30T06:00:00+00:00",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "proofs": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(anchor_cli, "load_manifest", lambda: [])
    monkeypatch.setattr(anchor_cli, "load_outcome_entries", lambda: [])

    rc = anchor_cli.cmd_outcome_insights(type("Args", (), {"limit": 10, "top": 3}))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Evidence artifacts" in out
    assert "bugbot_training: 1" in out


def test_discover_skips_malformed_json(tmp_path):
    training_dir = tmp_path / "outcomes" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "broken.json").write_text("{not json", encoding="utf-8")
    (training_dir / "bugbot-scenarios-a.json").write_text(
        json.dumps(
            {
                "runner": "bugbot",
                "scenario_pack": "v1",
                "timestamp": "2026-06-30T06:00:00+00:00",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "proofs": [],
            }
        ),
        encoding="utf-8",
    )
    rows = discover_bugbot_training_evidence(anchor_root=tmp_path, limit=5)
    assert len(rows) == 1


def test_normalize_benchmark_evidence_handles_non_dict_summary(tmp_path):
    record = normalize_benchmark_evidence(
        manifest_entry={
            "id": "broken-summary",
            "executed_at": "2026-06-29T18:00:00+00:00",
            "status": "complete",
            "artifact_json": "benchmarks/missing/benchmark.json",
            "results_summary": ["not", "a", "dict"],
        },
        anchor_root=tmp_path,
    )
    assert record is not None
    assert record["metrics"]["passed"] == 0
    assert record["metrics"]["failed"] == 0


def test_collect_evidence_records_sort_is_deterministic(tmp_path):
    training_dir = tmp_path / "outcomes" / "training"
    training_dir.mkdir(parents=True)
    for name, ts in (("bugbot-a", "2026-06-30T06:00:00+00:00"), ("bugbot-b", "2026-06-30T06:00:00+00:00")):
        (training_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "runner": "bugbot",
                    "scenario_pack": "v1",
                    "timestamp": ts,
                    "total": 1,
                    "passed": 1,
                    "failed": 0,
                    "proofs": [],
                }
            ),
            encoding="utf-8",
        )
    first = collect_evidence_records(anchor_root=tmp_path, manifest_entries=[], limit=10)
    second = collect_evidence_records(anchor_root=tmp_path, manifest_entries=[], limit=10)
    assert [row["run_id"] for row in first] == [row["run_id"] for row in second]


def test_normalize_bugbot_training_evidence_prefers_canonical_payload():
    canonical = build_bugbot_training_record(
        artifact_path="outcomes/training/bugbot-scenarios-canonical.json",
        timestamp="2026-06-30T07:00:00+00:00",
        run_id="bugbot-scenarios-canonical",
        scenario_pack="v1",
        total=2,
        passed=2,
        failed=0,
        proofs=[],
    )
    assert is_canonical_evidence(canonical)
    record = normalize_bugbot_training_evidence(
        path=Path("/tmp/ANCHOR/outcomes/training/bugbot-scenarios-canonical.json"),
        payload=canonical,
        anchor_root=Path("/tmp/ANCHOR"),
    )
    assert record["status"] == "proof_gate_passed"
    assert record["run_id"] == "bugbot-scenarios-canonical"
    assert record["artifact_path"] == "outcomes/training/bugbot-scenarios-canonical.json"


def test_normalize_bugbot_training_evidence_supports_legacy_payload():
    legacy = {
        "runner": "bugbot",
        "scenario_pack": "v1",
        "timestamp": "2026-06-30T05:38:57+00:00",
        "total": 1,
        "passed": 1,
        "failed": 0,
        "proofs": [{"id": "uups-initializer-takeover", "result": "PASS", "score": 92}],
    }
    record = normalize_bugbot_training_evidence(
        path=Path("/tmp/ANCHOR/outcomes/training/bugbot-scenarios-legacy.json"),
        payload=legacy,
        anchor_root=Path("/tmp/ANCHOR"),
    )
    assert record["status"] == "proof_gate_passed"
    assert record["source"]["scenario_pack"] == "v1"


def test_render_evidence_insights_uses_proof_gate_language():
    lines = render_evidence_insights(
        [
            {
                "kind": "bugbot_training",
                "timestamp": "2026-06-30T06:00:00+00:00",
                "target": "bugbot-scenario-pack/v1",
                "run_id": "bugbot-scenarios-a",
                "artifact_path": "outcomes/training/bugbot-scenarios-a.json",
                "status": "proof_gate_passed",
                "label": "BugBot v1: 1/1 curriculum proofs passed",
                "metrics": {"total": 1, "passed": 1, "failed": 0, "proofs": []},
            }
        ],
        top_n=3,
    )
    text = "\n".join(lines)
    assert "proof gate: proof_gate_passed" in text
    assert "curriculum proofs passed" in text
