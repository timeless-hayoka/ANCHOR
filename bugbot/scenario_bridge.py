"""Thin bridge from ANCHOR to bounty-bot BugBot scenario proofs."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ScenarioPackSummary:
    scenarios: int = 0
    passed: int = 0
    failed: int = 0
    scenario_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.scenarios > 0


@dataclass(frozen=True)
class ScenarioPackRunResult:
    bounty_bot_dir: Path
    exit_code: int
    output: str
    summary: ScenarioPackSummary


def _looks_like_bounty_bot(path: Path) -> bool:
    return (path / "scripts" / "bugbot_smoke.sh").is_file()


def resolve_bounty_bot_dir(*, anchor_root: Path) -> Path:
    """Resolve bounty-bot checkout from BOUNTY_BOT_DIR or ../bounty-bot sibling."""
    candidates: list[Path] = []
    env = os.environ.get("BOUNTY_BOT_DIR", "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(anchor_root.parent / "bounty-bot")

    checked: list[str] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        checked.append(str(resolved))
        if _looks_like_bounty_bot(resolved):
            return resolved

    raise FileNotFoundError(
        "bounty-bot not found. Set BOUNTY_BOT_DIR or place bounty-bot next to ANCHOR. "
        f"Checked: {', '.join(checked)}"
    )


def parse_scenario_pack_output(output: str) -> ScenarioPackSummary:
    """Parse the human summary emitted by bounty-bot/scripts/run_bugbot_scenarios.py."""
    text = output.replace("\r\n", "\n")
    rows: list[dict[str, Any]] = []
    scenarios = passed = failed = 0

    blocks = text.split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0] == "BugBot Scenario Pack":
            continue
        if lines[0] == "Summary:":
            for line in lines[1:]:
                if (match := re.match(r"(\d+)\s+scenarios?", line)):
                    scenarios = int(match.group(1))
                elif (match := re.match(r"(\d+)\s+passed", line)):
                    passed = int(match.group(1))
                elif (match := re.match(r"(\d+)\s+failed", line)):
                    failed = int(match.group(1))
            continue

        row: dict[str, Any] = {"scenario_id": lines[0]}
        for line in lines[1:]:
            if line.startswith("Detector:"):
                row["detector_score"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("Expected:"):
                row["expected_severity"] = line.split(":", 1)[1].strip()
            elif line.startswith("Proof:"):
                row["proof"] = line.split(":", 1)[1].strip()
        if "proof" in row:
            rows.append(row)

    return ScenarioPackSummary(
        scenarios=scenarios,
        passed=passed,
        failed=failed,
        scenario_rows=rows,
    )


def run_scenario_pack(*, bounty_bot_dir: Path) -> ScenarioPackRunResult:
    """Run bounty-bot/scripts/bugbot_smoke.sh (Foundry + detector proof pack)."""
    smoke = bounty_bot_dir / "scripts" / "bugbot_smoke.sh"
    if not smoke.is_file():
        raise FileNotFoundError(f"BugBot smoke script not found: {smoke}")

    env = os.environ.copy()
    env.setdefault("BOUNTY_BOT_DIR", str(bounty_bot_dir))
    completed = subprocess.run(
        ["bash", str(smoke)],
        cwd=str(bounty_bot_dir),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    output = (completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")
    return ScenarioPackRunResult(
        bounty_bot_dir=bounty_bot_dir,
        exit_code=completed.returncode,
        output=output.strip(),
        summary=parse_scenario_pack_output(output),
    )


def load_scenario_pack_label(*, bounty_bot_dir: Path) -> str:
    """Read scenario pack version from bounty-bot hunt_pack/bugbot/scenario_index.json."""
    index_path = bounty_bot_dir / "hunt_pack" / "bugbot" / "scenario_index.json"
    if not index_path.is_file():
        return "v1"
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "v1"
    version = data.get("version", 1)
    return f"v{version}"


def build_scenario_pack_artifact(
    *,
    run: ScenarioPackRunResult,
    timestamp: str,
    scenario_pack: str,
) -> dict[str, Any]:
    """Canonical structured artifact for dashboards, diffs, and outcome insights."""
    proofs: list[dict[str, Any]] = []
    for row in run.summary.scenario_rows:
        proof: dict[str, Any] = {
            "id": row["scenario_id"],
            "result": row.get("proof", ""),
        }
        if "detector_score" in row:
            proof["score"] = row["detector_score"]
        proofs.append(proof)

    return {
        "runner": "bugbot",
        "scenario_pack": scenario_pack,
        "timestamp": timestamp,
        "total": run.summary.scenarios,
        "passed": run.summary.passed,
        "failed": run.summary.failed,
        "proofs": proofs,
    }


def write_scenario_pack_artifact(
    *,
    anchor_root: Path,
    run: ScenarioPackRunResult,
    utcnow_iso: Callable[[], str],
) -> Path:
    """Write structured JSON under outcomes/training/ (every scenario run)."""
    training_dir = anchor_root / "outcomes" / "training"
    training_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utcnow_iso()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = training_dir / f"bugbot-scenarios-{stamp}.json"
    payload = build_scenario_pack_artifact(
        run=run,
        timestamp=timestamp,
        scenario_pack=load_scenario_pack_label(bounty_bot_dir=run.bounty_bot_dir),
    )
    artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return artifact


def record_scenario_pack_outcome(
    *,
    anchor_root: Path,
    artifact: Path,
    run: ScenarioPackRunResult,
    append_outcome: Callable[[dict[str, Any]], None],
    utcnow_iso: Callable[[], str],
    make_outcome_id: Callable[[str, str], str],
) -> None:
    """Append outcome ledger entry pointing at a structured training artifact."""
    status = "published" if run.summary.success else "rejected"
    lesson = (
        f"BugBot scenario pack {run.summary.passed}/{run.summary.scenarios} passed"
        if run.summary.scenarios
        else "BugBot scenario pack produced no runnable scenarios"
    )
    append_outcome(
        {
            "id": make_outcome_id("benchmark", "bugbot-scenario-pack"),
            "timestamp": utcnow_iso(),
            "type": "benchmark",
            "status": status,
            "target": "bugbot-scenario-pack",
            "run_id": artifact.stem,
            "benchmark_id": artifact.stem,
            "lesson": lesson,
            "note": "Proof-backed BugBot curriculum run via bounty-bot smoke",
            "evidence": str(artifact.relative_to(anchor_root)),
            "links": {
                "artifact": str(artifact.relative_to(anchor_root)),
                "benchmark": "",
                "pr": "",
                "issue": "",
                "report": "",
            },
        }
    )


def archive_scenario_pack_run(
    *,
    anchor_root: Path,
    run: ScenarioPackRunResult,
    record_outcome: bool,
    append_outcome: Callable[[dict[str, Any]], None],
    utcnow_iso: Callable[[], str],
    make_outcome_id: Callable[[str, str], str],
) -> Path:
    """Write structured artifact; optionally append outcome ledger entry."""
    artifact = write_scenario_pack_artifact(
        anchor_root=anchor_root,
        run=run,
        utcnow_iso=utcnow_iso,
    )
    if record_outcome:
        record_scenario_pack_outcome(
            anchor_root=anchor_root,
            artifact=artifact,
            run=run,
            append_outcome=append_outcome,
            utcnow_iso=utcnow_iso,
            make_outcome_id=make_outcome_id,
        )
    return artifact
