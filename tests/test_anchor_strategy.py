from __future__ import annotations

import json
from pathlib import Path

import anchor_strategy


def test_strategy_recommends_unstable_open_challenge(tmp_path: Path):
    entries = [
        {
            "id": "run-1",
            "publication_tier": "published",
            "executed_at": "2026-06-01T00:00:00+00:00",
            "level": "Phase 1",
            "results_summary": {"passed": 1, "failed": 0, "timed_out": 1},
            "artifact_json": "runs/run-1/benchmark.json",
        },
        {
            "id": "run-2",
            "publication_tier": "published",
            "executed_at": "2026-06-02T00:00:00+00:00",
            "level": "Phase 1",
            "results_summary": {"passed": 1, "failed": 0, "timed_out": 1},
            "artifact_json": "runs/run-2/benchmark.json",
        },
    ]
    for run_id, results in [
        (
            "run-1",
            [
                {"challenge": "withdrawal", "status": "PASSED"},
                {"challenge": "wallet-mining", "status": "TIMED_OUT", "timed_out": True},
            ],
        ),
        (
            "run-2",
            [
                {"challenge": "withdrawal", "status": "PASSED"},
                {"challenge": "wallet-mining", "status": "TIMED_OUT", "timed_out": True},
            ],
        ),
    ]:
        run_dir = tmp_path / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "benchmark.json").write_text(json.dumps({"summary": {}, "results": results}))

    outcomes = [
        {"timestamp": "2026-06-02T01:00:00+00:00", "lesson": "Repeated timeout on wallet mining brute force"},
    ]
    payload = anchor_strategy.compute_strategy(entries, outcomes, root=tmp_path, top_n=3)
    assert payload["next_hunt"]["challenge"] == "wallet-mining"
    rendered = anchor_strategy.render_strategy(payload)
    assert "Wallet Mining" in rendered
    assert "Repeated timeout" in rendered


def test_categorize_lesson_timeout():
    assert anchor_strategy.categorize_lesson("Repeated timeout on CREATE2 search") == "Repeated timeout"
