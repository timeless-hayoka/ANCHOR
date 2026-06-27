from __future__ import annotations

import json
from pathlib import Path

import anchor_trends


def _entry(run_id: str, executed_at: str, passed: int, failed: int, timed_out: int, results: list[dict]) -> dict:
    return {
        "id": run_id,
        "publication_tier": "published",
        "executed_at": executed_at,
        "target": "damn-vulnerable-defi",
        "level": "Phase 1",
        "results_summary": {
            "passed": passed,
            "failed": failed,
            "timed_out": timed_out,
        },
        "artifact_json": f"runs/{run_id}/benchmark.json",
    }


def test_reproduction_rate_from_summary():
    assert anchor_trends.reproduction_rate({"passed": 9, "failed": 1, "timed_out": 0}) == 0.9
    assert anchor_trends.reproduction_rate({}) is None


def test_compute_benchmark_trends_improvement_and_instability(tmp_path: Path):
    root = tmp_path
    for run_id, executed_at, passed, failed, timed_out, results in [
        (
            "run-1",
            "2026-06-01T00:00:00+00:00",
            1,
            1,
            1,
            [
                {"challenge": "withdrawal", "status": "FAILED"},
                {"challenge": "wallet-mining", "status": "TIMED_OUT", "timed_out": True},
            ],
        ),
        (
            "run-2",
            "2026-06-02T00:00:00+00:00",
            2,
            0,
            1,
            [
                {"challenge": "withdrawal", "status": "PASSED"},
                {"challenge": "wallet-mining", "status": "FAILED"},
            ],
        ),
    ]:
        run_dir = root / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "benchmark.json").write_text(json.dumps({"summary": {}, "results": results}))

    entries = [
        _entry("run-1", "2026-06-01T00:00:00+00:00", 1, 1, 1, []),
        _entry("run-2", "2026-06-02T00:00:00+00:00", 2, 0, 1, []),
    ]
    trends = anchor_trends.compute_benchmark_trends(entries, root=root, limit=10)

    assert trends["published_count"] == 2
    assert trends["average_reproduction_rate"] == 0.5
    assert trends["trend_direction"] == "up"
    assert trends["top_improved_challenge"]["challenge"] == "withdrawal"
    assert trends["most_unstable_challenge"]["challenge"] == "wallet-mining"

    rendered = anchor_trends.render_benchmark_trends(trends)
    assert "Average Reproduction Rate" in rendered
    assert "Withdrawal" in rendered
    assert "Wallet Mining" in rendered


def test_render_benchmark_trends_empty():
    rendered = anchor_trends.render_benchmark_trends({"published_count": 0})
    assert "No published benchmark runs" in rendered
