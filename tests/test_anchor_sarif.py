from __future__ import annotations

import json
from pathlib import Path

from anchor_sarif.adapters.aderyn import AderynAdapter
from anchor_sarif.adapters.halmos import HalmosAdapter
from anchor_sarif.adapters.mythril import MythrilAdapter
from anchor_sarif.assumptions import extract_protocol_assumptions
from anchor_sarif.drift import measure_drift
from anchor_sarif.economic_context import assess_economic_context
from anchor_sarif.fp_heuristics import assess_signal_noise
from anchor_sarif.future_state import rewrite_finding
from anchor_sarif.incentive_surface import map_incentive_surface
from anchor_sarif.mev_lifecycle import model_mev_lifecycle
from anchor_sarif.parser import Finding, parse_sarif_payload
from anchor_sarif.pipeline import SARIFProcessingPipeline
from anchor_sarif.research_loop import build_research_loop
from anchor_sarif.universe import compare_universes
from anchor_sarif.validator_bridge import annotate_finding, validate_candidate


def test_aderyn_adapter_parses_issues():
    payload = {
        "issues": [
            {
                "title": "Reentrancy in withdraw",
                "swc_id": "SWC-107",
                "severity": "high",
                "location": {"file_path": "Vault.sol", "line": 42},
            }
        ]
    }
    findings = AderynAdapter().parse(payload)
    assert len(findings) == 1
    assert findings[0].tool == "aderyn"
    assert findings[0].rule_id == "SWC-107"
    assert findings[0].file_path == "Vault.sol"


def test_mythril_adapter_parses_issues():
    payload = {
        "issues": [
            {
                "title": "Integer Overflow",
                "description": "Possible overflow in transfer",
                "swc-id": "SWC-101",
                "filename": "Token.sol",
                "lineno": 10,
            }
        ]
    }
    findings = MythrilAdapter().parse(payload)
    assert len(findings) == 1
    assert findings[0].tool == "mythril"
    assert "Overflow" in findings[0].message


def test_halmos_adapter_only_reports_failed_invariants():
    payload = {
        "results": [
            {"name": "totalSupplyNeverZero", "status": "passed"},
            {"name": "balanceConservation", "status": "failed", "filename": "Bank.sol", "line": 5},
        ]
    }
    findings = HalmosAdapter().parse(payload)
    assert len(findings) == 1
    assert findings[0].properties["is_invariant"] is True


def test_pipeline_processes_ensemble(tmp_path: Path):
    db_path = tmp_path / "findings.db"
    pipeline = SARIFProcessingPipeline(db_path=db_path, enable_semantic_clustering=False)

    tool_outputs = {
        "aderyn": {
            "issues": [
                {
                    "title": "Unchecked owner",
                    "severity": "medium",
                    "location": {"file_path": "Ownable.sol", "line": 3},
                }
            ]
        },
        "mythril": {
            "issues": [
                {
                    "title": "Unchecked owner",
                    "description": "Missing onlyOwner",
                    "filename": "Ownable.sol",
                    "lineno": 3,
                }
            ]
        },
    }

    enriched = pipeline.process_ensemble(tool_outputs)
    assert len(enriched) >= 1
    assert db_path.exists()


def test_parse_sarif_payload_minimal():
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "slither"}},
                "results": [
                    {
                        "ruleId": "reentrancy-eth",
                        "message": {"text": "Reentrancy vulnerability"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "Vault.sol"},
                                    "region": {"startLine": 12},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    findings = parse_sarif_payload(payload)
    assert len(findings) == 1
    assert findings[0].tool == "slither"
    assert findings[0].start_line == 12


def test_signal_filter_flags_test_file():
    finding = Finding(
        tool="slither",
        rule_id="naming-convention",
        level="note",
        message="Variable name should be in mixedCase",
        file_path="test/Vault.t.sol",
        start_line=1,
    )
    result = assess_signal_noise(finding)
    assert result["is_likely_false_positive"]
    assert result["suggested_action"] in {"discard", "review"}
    assert result["confidence"] >= 0.5


def test_signal_filter_promotes_halmos_invariant():
    finding = Finding(
        tool="halmos",
        rule_id="halmos-balanceConservation",
        level="warning",
        message="Invariant violation: balanceConservation",
        file_path="Bank.sol",
        start_line=5,
        properties={"is_invariant": True},
    )
    result = assess_signal_noise(finding)
    assert not result["is_likely_false_positive"]
    assert result["suggested_action"] == "promote"


def test_signal_filter_discards_generic_slither_unchecked_call():
    finding = Finding(
        tool="slither",
        rule_id="unchecked-call",
        level="warning",
        message="Low-level call may be unsafe",
        file_path="src/Vault.sol",
        start_line=88,
        snippet='ok = payable(msg.sender).call{value: amount}("");',
    )
    result = assess_signal_noise(finding)
    assert result["is_likely_false_positive"]
    assert result["suggested_action"] == "discard"
    assert result["confidence"] >= 0.7


def test_signal_filter_promotes_exploit_specific_unchecked_call():
    finding = Finding(
        tool="slither",
        rule_id="unchecked-call",
        level="warning",
        message="Unchecked low-level call may allow reentrancy drain of vault funds",
        file_path="src/Vault.sol",
        start_line=88,
        snippet="target.call(data);",
    )
    result = assess_signal_noise(finding)
    assert not result["is_likely_false_positive"]
    assert result["suggested_action"] == "promote"


def test_pipeline_filters_high_confidence_false_positives(tmp_path):
    db_path = tmp_path / "findings.db"
    pipeline = SARIFProcessingPipeline(
        db_path=db_path,
        enable_semantic_clustering=False,
        filter_false_positives=True,
        fp_discard_threshold=0.5,
    )

    tool_outputs = {
        "slither": {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "slither"}},
                    "results": [
                        {
                            "ruleId": "naming-convention",
                            "level": "note",
                            "message": {"text": "Parameter naming"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "test/Mock.sol"},
                                        "region": {"startLine": 1},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    }

    enriched = pipeline.process(tool_outputs=tool_outputs)
    assert len(enriched) == 0
    assert pipeline.last_run_stats.signal_discarded >= 1



def test_future_state_rewrite_marks_finding():
    finding = Finding(
        tool="slither",
        rule_id="sandwich-ordering",
        level="warning",
        message="Transaction ordering assumptions",
        file_path="Pool.sol",
        start_line=8,
    )
    rewritten = rewrite_finding(finding, future_state="ePBS + inclusion lists")
    assert rewritten is not finding
    assert rewritten.properties["future_state"]["future_state"] == "ePBS + inclusion lists"
    assert "future-state" in rewritten.properties["tags"]


def test_economic_context_and_validation_bridge():
    finding = Finding(
        tool="slither",
        rule_id="sandwich-ordering",
        level="warning",
        message="Possible sandwich and ordering issue",
        file_path="Pool.sol",
        start_line=8,
    )
    assessment = assess_economic_context(finding, future_state="ePBS + inclusion lists")
    decision = validate_candidate(finding, economic_assessment=assessment)
    annotated = annotate_finding(finding)
    assert assessment.future_relevance_score >= 0.1
    assert decision.status in {"promote", "review", "reject"}
    assert "economic_context" in annotated
    assert "validation" in annotated


def test_parallel_universe_and_drift():
    current = Finding(
        tool="slither",
        rule_id="liquidation-timing",
        level="warning",
        message="Liquidation timing depends on ordering",
        file_path="Vault.sol",
        start_line=12,
        properties={"semantic_cluster": {"cluster_id": 1}},
    )
    future = Finding(
        tool="slither",
        rule_id="liquidation-timing",
        level="warning",
        message="Liquidation timing depends on ordering",
        file_path="Vault.sol",
        start_line=12,
        properties={"semantic_cluster": {"cluster_id": 2}},
    )
    universe = compare_universes([current], future_state="ePBS + inclusion lists")
    drift = measure_drift([current], [future])
    assert universe[0].future_relevance >= universe[0].current_relevance
    assert drift[0].moved is True


def test_assumption_and_lifecycle_modules():
    cards = extract_protocol_assumptions("The protocol assumes transaction ordering and liquidations are stable")
    lifecycle = model_mev_lifecycle("sandwich")
    surface = map_incentive_surface(["sandwich", "liquidation"])
    assert cards
    assert lifecycle.future_world
    assert len(surface) == 2


def test_research_loop_builds_queue():
    finding = Finding(
        tool="slither",
        rule_id="oracle-delay",
        level="warning",
        message="Oracle delay may affect liquidation ordering",
        file_path="Vault.sol",
        start_line=12,
    )
    loop = build_research_loop([finding])
    assert loop.queue
    assert loop.universe_report
    assert loop.assumption_cards
    assert loop.mev_reports


def test_pipeline_applies_future_state_and_economic_hooks(tmp_path):
    db_path = tmp_path / "findings.db"
    pipeline = SARIFProcessingPipeline(
        db_path=db_path,
        enable_semantic_clustering=False,
        future_state_rewriter=rewrite_finding,
        economic_validator=lambda finding: assess_economic_context(finding, future_state="ePBS + inclusion lists").to_dict(),
    )

    tool_outputs = {
        "slither": {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "slither"}},
                    "results": [
                        {
                            "ruleId": "oracle-delay",
                            "level": "warning",
                            "message": {"text": "Oracle delay may affect liquidation ordering"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "Vault.sol"},
                                        "region": {"startLine": 12},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    }

    enriched = pipeline.process(tool_outputs=tool_outputs)
    assert enriched
    assert enriched[0].finding.properties["future_state"]["future_state"] == "ePBS + inclusion lists"
    assert "economic_context" in enriched[0].finding.properties
