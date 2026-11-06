"""Deterministic integration controls; fixture evidence is not on-chain proof."""
import copy
import pytest
from trinity_proof_handoff import HandoffRejected, review_case


def fixtures():
    finder = dict(case_id="lab-case-1", target="fixture/protocol", claim="share invariant",
                  scope_status="authorized", scope="authorized local fixture",
                  scope_evidence_ref="scope/lab-grant.json", duplicate_status="clear",
                  mechanism="accounting invariant breaks", falsifier="balanced output")
    foundry = dict(case_id="lab-case-1", target="fixture/protocol",
                   scope_evidence_ref="scope/lab-grant.json",
                   status="reproduced_real", negative_control_passed=True,
                   source_equivalence="proven", chain_id=10, block_number=120000000,
                   block_hash="0x" + "a" * 64, runtime_sha256="b" * 64,
                   repro_plan="run deterministic fork assertions", actor="foundry",
                   evidence_refs=["evidence/local-fixture.json"])
    watcher = dict(case_id="lab-case-1", verdict="validated", actor="watcher",
                   challenge="independent falsifier and negative control checked",
                   reviewed_evidence_refs=["evidence/local-fixture.json"],
                   evidence_refs=["reviews/watcher-fixture.json"])
    council = dict(case_id="lab-case-1", verdict="accepted", actor="council",
                   impact_boundary="fixture-only state invariant discrepancy",
                   reviewed_evidence_refs=["evidence/local-fixture.json"],
                   evidence_refs=["reviews/council-fixture.json"])
    return finder, foundry, watcher, council


def test_full_lab_handoff_stops_at_council_not_report_ready():
    record = review_case(*fixtures())
    assert record.state == "council_accepted"
    assert [e.to_state for e in record.events] == [
        "hypothesis", "repro_attempted", "reproduced_real",
        "watcher_reviewed", "council_accepted",
    ]
    assert record.scope_status == "authorized"
    assert record.watcher_verdict == "validated"


@pytest.mark.parametrize("artifact,field,value", [
    (0, "scope_status", "unknown"),
    (0, "duplicate_status", "unknown"),
    (0, "scope_evidence_ref", ""),
    (1, "case_id", "different"),
    (1, "target", "other/target"),
    (1, "scope_evidence_ref", "wrong"),
    (1, "status", "mocked_only"),
    (1, "negative_control_passed", False),
    (1, "source_equivalence", "unknown"),
    (1, "chain_id", True),
    (1, "block_hash", "0x123"),
    (1, "runtime_sha256", "x" * 64),
    (1, "evidence_refs", []),
    (1, "evidence_refs", ["duplicate", "duplicate"]),
    (2, "verdict", "discredited"),
    (2, "verdict", "inconclusive"),
    (2, "actor", "foundry"),
    (2, "reviewed_evidence_refs", ["evidence/stale.json"]),
    (2, "evidence_refs", []),
    (3, "verdict", "pending"),
    (3, "actor", "watcher"),
    (3, "reviewed_evidence_refs", ["evidence/unrelated.json"]),
    (3, "evidence_refs", []),
])
def test_planted_failures_are_rejected(artifact, field, value):
    pieces = list(fixtures())
    pieces[artifact][field] = value
    with pytest.raises(HandoffRejected):
        review_case(*pieces)


def test_finder_metadata_not_promoted_by_unrelated_fixture():
    f, p, w, c = fixtures()
    p["case_id"] = "other-case"
    with pytest.raises(HandoffRejected, match="identity mismatch"):
        review_case(f, p, w, c)


def test_inputs_unchanged():
    original = fixtures()
    snapshot = copy.deepcopy(original)
    review_case(*original)
    assert original == snapshot
