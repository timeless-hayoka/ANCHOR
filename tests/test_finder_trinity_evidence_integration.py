"""Finder -> oracle triage -> Trinity -> evidence fail-closed integration.

No external network, storage override, synthetic scope grant, or report promotion.
"""
import json

import pytest

import github_discovery as finder
from extra_liquidation_eligibility import TokenObservation, evaluate_candidate
from outcome_evidence import collect_evidence_records
from trinity_lead_state_machine import (
    LeadRecord, LeadTransitionError, apply_transition, validate_lead
)

BLOCK = 120_000_000
TOKEN_0 = "0x" + "11" * 20
TOKEN_1 = "0x" + "22" * 20
ORACLE = "0x" + "33" * 20


def test_discovery_to_trinity_is_signal_even_if_oracle_risk_is_high(tmp_path):
    repo = {"full_name": "fixture/protocol", "language": "Solidity",
            "topics": ["foundry", "security"], "open_issues_count": 100}
    rank = finder.compute_repo_score(repo, "audit scope foundry oracle" * 100, ["solidity"])
    assert rank.review_state == "Needs scope confirmation"

    def token(addr, units):
        return TokenObservation(addr, units, 6, 10**18, BLOCK,
                                ORACLE, "sampled-protocol-price", True)
    triage = evaluate_candidate(
        chain_id=10, block=BLOCK, vault_id=3, position_id=16,
        threshold_bps=8333,
        collateral=(token(TOKEN_0, 100_000_000),),
        debt=(token(TOKEN_1, 95_000_000),),
    )
    assert triage.status == "AT_RISK_UNCONFIRMED"

    lead = LeadRecord(lead_id="candidate_fixture", target=repo["full_name"],
                      title="Historical oracle risk needs proof")
    assert lead.scope_status == "unknown"
    assert validate_lead(lead) == []
    with pytest.raises(LeadTransitionError, match="illegal transition"):
        apply_transition(lead, to_state="reproduced_real", actor="triage",
                         reason=triage.status, event_id="bypass_1")

    # Evidence dashboards can display unrelated fixture executions without
    # turning an unverified risk hypothesis into a proven finding.
    training_dir = tmp_path / "outcomes" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "bugbot-scenarios-fixture.json").write_text(json.dumps({
        "runner": "bugbot", "scenario_pack": "fixture",
        "timestamp": "2026-11-04T12:00:00+00:00",
        "total": 1, "passed": 1, "failed": 0, "proofs": []
    }), encoding="utf-8")
    evidence = collect_evidence_records(
        anchor_root=tmp_path, manifest_entries=[], limit=10
    )
    assert any(entry["kind"] == "bugbot_training" for entry in evidence)
    assert lead.state == "signal"
    assert lead.evidence_refs == []
    with pytest.raises(LeadTransitionError, match="illegal transition"):
        apply_transition(lead, to_state="report_ready", actor="dashboard",
                         reason="other test passed", event_id="bypass_2")
