"""Exercise the real CLI entry point with local fixture bundles."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "trinity_review_handoff.py"


def bundle():
    ref = "evidence/lab.json"
    return {
        "finder": {
            "case_id": "cli-fixture", "target": "fixture/local",
            "claim": "invariant", "scope_status": "authorized",
            "scope": "local fixture", "scope_evidence_ref": "scope/lab.json",
            "duplicate_status": "clear", "mechanism": "accounting check",
            "falsifier": "no discrepancy",
        },
        "foundry": {
            "case_id": "cli-fixture", "target": "fixture/local",
            "scope_evidence_ref": "scope/lab.json",
            "status": "reproduced_real", "negative_control_passed": True,
            "source_equivalence": "proven", "chain_id": 10,
            "block_number": 120000000, "block_hash": "0x" + "a" * 64,
            "runtime_sha256": "b" * 64,
            "repro_plan": "lab assertion", "actor": "foundry",
            "evidence_refs": [ref],
        },
        "watcher": {
            "case_id": "cli-fixture", "verdict": "validated", "actor": "watcher",
            "challenge": "independent control check",
            "reviewed_evidence_refs": [ref],
            "evidence_refs": ["review/watcher.json"],
        },
        "council": {
            "case_id": "cli-fixture", "verdict": "accepted", "actor": "council",
            "impact_boundary": "lab-only impact",
            "reviewed_evidence_refs": [ref],
            "evidence_refs": ["review/council.json"],
        },
    }


def invoke(source, dest):
    return subprocess.run([sys.executable, str(CLI), "--bundle", str(source),
                           "--output", str(dest)], text=True, capture_output=True,
                          timeout=15, cwd=ROOT, check=False)


def test_cli_positive_and_no_overwrite(tmp_path):
    source, dest = tmp_path / "bundle.json", tmp_path / "result.json"
    source.write_text(json.dumps(bundle()), encoding="utf-8")
    run = invoke(source, dest)
    assert run.returncode == 0, run.stderr
    result = json.loads(dest.read_text())
    assert result["lead"]["state"] == "council_accepted"
    assert result["finding_confirmed_onchain"] is False
    original = dest.read_bytes()
    assert invoke(source, dest).returncode == 2
    assert dest.read_bytes() == original


def test_cli_planted_false_proof_cannot_write(tmp_path):
    source, dest = tmp_path / "bundle.json", tmp_path / "result.json"
    bad = bundle()
    bad["foundry"]["negative_control_passed"] = False
    source.write_text(json.dumps(bad), encoding="utf-8")
    run = invoke(source, dest)
    assert run.returncode == 2
    assert not dest.exists()


def test_cli_malformed_json_rejected(tmp_path):
    source, dest = tmp_path / "bundle.json", tmp_path / "result.json"
    source.write_text("{")
    run = invoke(source, dest)
    assert run.returncode == 2
    assert not dest.exists()
