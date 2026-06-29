from __future__ import annotations

from anchor_work_queue import load_work_queue, render_work_queue, work_queue_summary


def test_work_queue_loader_parses_repo_doc():
    queue = load_work_queue()
    summary = work_queue_summary(queue)

    assert summary["kind"] == "anchor.work_queue"
    assert summary["counts"]["active"] == 1
    assert summary["counts"]["ready"] == 2
    assert summary["counts"]["blocked"] == 0
    assert summary["counts"]["completed"] == 1
    assert summary["top_item"]["id"] == "A-001"
    assert summary["top_item"]["acceptance_criteria"][0] == "At least one benchmark corpus is selected and documented."
    completed = next(item for item in summary["items"] if item["id"] == "A-000")
    assert completed["evidence"][0] == "Commit: `e1af9f1`"
    assert "docs/ANCHOR_WORK_QUEUE.md" in summary["queue_path"]


def test_work_queue_renderer_mentions_key_entries():
    rendered = render_work_queue()

    assert "ANCHOR Work Queue" in rendered
    assert "A-001" in rendered
    assert "A-000" in rendered
    assert "Benchmark the SARIF pipeline against known findings" in rendered
