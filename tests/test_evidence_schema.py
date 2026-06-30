from __future__ import annotations

from evidence_schema import (
    EVIDENCE_SCHEMA_VERSION,
    EvidenceRecord,
    build_bugbot_training_record,
    bugbot_proof_gate_status,
    insight_record_from_canonical,
    is_canonical_evidence,
    normalize_evidence_status,
)


def test_normalize_evidence_status_maps_legacy_aliases():
    assert normalize_evidence_status("proof_gate_pass") == "proof_gate_passed"
    assert normalize_evidence_status("proof_gate_fail") == "proof_gate_failed"
    assert normalize_evidence_status("published") == "published"
    assert normalize_evidence_status("mystery") == "unknown"


def test_build_bugbot_training_record_emits_canonical_and_legacy_fields():
    payload = build_bugbot_training_record(
        artifact_path="outcomes/training/bugbot-scenarios-test.json",
        timestamp="2026-06-30T06:00:00+00:00",
        run_id="bugbot-scenarios-test",
        scenario_pack="v1",
        total=1,
        passed=1,
        failed=0,
        proofs=[{"id": "uups-initializer-takeover", "result": "PASS", "score": 92}],
    )
    assert is_canonical_evidence(payload)
    assert payload["kind"] == "bugbot_training"
    assert payload["status"] == "proof_gate_passed"
    assert payload["runner"] == "bugbot"
    assert payload["total"] == 1
    assert payload["proofs"][0]["id"] == "uups-initializer-takeover"


def test_evidence_record_roundtrip():
    record = EvidenceRecord(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        kind="bugbot_training",
        artifact_path="outcomes/training/x.json",
        timestamp="2026-06-30T06:00:00+00:00",
        target="bugbot-scenario-pack/v1",
        run_id="bugbot-scenarios-x",
        status="proof_gate_passed",
        metrics={"total": 1, "passed": 1, "failed": 0, "proofs": []},
        links={"artifact": "outcomes/training/x.json"},
        source={"runner": "bugbot", "scenario_pack": "v1"},
    )
    restored = EvidenceRecord.from_dict(record.to_dict())
    assert restored.to_dict() == record.to_dict()


def test_bugbot_proof_gate_status_vocabulary():
    assert bugbot_proof_gate_status(total=1, passed=1, failed=0) == "proof_gate_passed"
    assert bugbot_proof_gate_status(total=2, passed=1, failed=1) == "proof_gate_failed"


def test_insight_record_from_canonical_adds_label():
    payload = build_bugbot_training_record(
        artifact_path="outcomes/training/bugbot-scenarios-test.json",
        timestamp="2026-06-30T06:00:00+00:00",
        run_id="bugbot-scenarios-test",
        scenario_pack="v1",
        total=1,
        passed=1,
        failed=0,
        proofs=[],
    )
    row = insight_record_from_canonical(payload)
    assert row["status"] == "proof_gate_passed"
    assert "curriculum proofs passed" in row["label"]
