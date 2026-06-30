from __future__ import annotations

import json
from pathlib import Path

import pytest

from bugbot.scenario_bridge import (
    archive_scenario_pack_run,
    build_scenario_pack_artifact,
    parse_scenario_pack_output,
    resolve_bounty_bot_dir,
    run_scenario_pack,
    ScenarioPackRunResult,
    ScenarioPackSummary,
)


SAMPLE_OUTPUT = """\
No files changed, compilation skipped

Ran 2 tests for test/UUPSInitializerTakeover.t.sol:TestUUPSInitializerTakeover
Suite result: ok. 2 passed; 0 failed; 0 skipped

BugBot Scenario Pack

uups-initializer-takeover
Detector: 92
Expected: critical
Proof: PASS

Summary:
1 scenarios
1 passed
0 failed
"""


def test_parse_scenario_pack_output():
    summary = parse_scenario_pack_output(SAMPLE_OUTPUT)
    assert summary.scenarios == 1
    assert summary.passed == 1
    assert summary.failed == 0
    assert summary.success is True
    assert summary.scenario_rows[0]["scenario_id"] == "uups-initializer-takeover"
    assert summary.scenario_rows[0]["detector_score"] == 92


def test_resolve_bounty_bot_dir_from_sibling(tmp_path, monkeypatch):
    anchor = tmp_path / "ANCHOR"
    anchor.mkdir()
    bounty = tmp_path / "bounty-bot"
    (bounty / "scripts").mkdir(parents=True)
    (bounty / "scripts" / "bugbot_smoke.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.delenv("BOUNTY_BOT_DIR", raising=False)
    assert resolve_bounty_bot_dir(anchor_root=anchor) == bounty.resolve()


def test_resolve_bounty_bot_dir_prefers_env(tmp_path, monkeypatch):
    anchor = tmp_path / "ANCHOR"
    anchor.mkdir()
    env_path = tmp_path / "custom-bounty"
    (env_path / "scripts").mkdir(parents=True)
    (env_path / "scripts" / "bugbot_smoke.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setenv("BOUNTY_BOT_DIR", str(env_path))
    assert resolve_bounty_bot_dir(anchor_root=anchor) == env_path.resolve()


def test_build_scenario_pack_artifact_matches_canonical_schema():
    summary = parse_scenario_pack_output(SAMPLE_OUTPUT)
    run = ScenarioPackRunResult(
        bounty_bot_dir=Path("/tmp/bounty-bot"),
        exit_code=0,
        output=SAMPLE_OUTPUT,
        summary=summary,
    )
    payload = build_scenario_pack_artifact(
        run=run,
        timestamp="2026-06-26T12:00:00+00:00",
        scenario_pack="v1",
    )
    assert payload == {
        "runner": "bugbot",
        "scenario_pack": "v1",
        "timestamp": "2026-06-26T12:00:00+00:00",
        "total": 1,
        "passed": 1,
        "failed": 0,
        "proofs": [{"id": "uups-initializer-takeover", "result": "PASS", "score": 92}],
    }


def test_archive_scenario_pack_run_writes_training_artifact(tmp_path):
    anchor = tmp_path / "ANCHOR"
    anchor.mkdir()
    run = ScenarioPackRunResult(
        bounty_bot_dir=tmp_path / "bounty-bot",
        exit_code=0,
        output=SAMPLE_OUTPUT,
        summary=parse_scenario_pack_output(SAMPLE_OUTPUT),
    )
    ledger: list[dict] = []

    artifact = archive_scenario_pack_run(
        anchor_root=anchor,
        run=run,
        record_outcome=True,
        append_outcome=ledger.append,
        utcnow_iso=lambda: "2026-06-26T12:00:00+00:00",
        make_outcome_id=lambda kind, target: f"{kind}-{target}",
    )

    assert artifact.exists()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["runner"] == "bugbot"
    assert payload["total"] == 1
    assert payload["proofs"][0]["id"] == "uups-initializer-takeover"
    assert ledger and ledger[0]["target"] == "bugbot-scenario-pack"


def test_cmd_bugbot_scenarios_delegates(monkeypatch, capsys, tmp_path):
    import anchor_cli

    anchor = tmp_path / "ANCHOR"
    anchor.mkdir()
    bounty = tmp_path / "bounty-bot"
    (bounty / "scripts").mkdir(parents=True)
    (bounty / "scripts" / "bugbot_smoke.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    monkeypatch.setattr(anchor_cli, "ROOT", anchor)
    monkeypatch.setattr(
        anchor_cli,
        "resolve_bounty_bot_dir",
        lambda anchor_root: bounty.resolve(),
    )
    monkeypatch.setattr(
        anchor_cli,
        "run_scenario_pack",
        lambda bounty_bot_dir: ScenarioPackRunResult(
            bounty_bot_dir=bounty_bot_dir,
            exit_code=0,
            output=SAMPLE_OUTPUT,
            summary=parse_scenario_pack_output(SAMPLE_OUTPUT),
        ),
    )

    monkeypatch.setattr(
        anchor_cli,
        "archive_scenario_pack_run",
        lambda **kwargs: tmp_path / "ANCHOR" / "outcomes" / "training" / "bugbot-scenarios-test.json",
    )

    rc = anchor_cli.cmd_bugbot_scenarios(type("Args", (), {"all": True, "record": False, "json": False}))
    out = capsys.readouterr().out
    assert rc == 0
    assert "BugBot Scenario Pack" in out
    assert "1 passed" in out


def test_parser_accepts_bugbot_scenarios():
    import anchor_cli

    parser = anchor_cli.create_parser()
    args = parser.parse_args(["bugbot", "scenarios", "--all", "--record"])
    assert args.command == "bugbot"
    assert args.bugbot_command == "scenarios"
    assert args.all is True
    assert args.record is True
