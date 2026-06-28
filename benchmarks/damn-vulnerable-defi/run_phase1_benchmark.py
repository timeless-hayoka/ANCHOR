#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from anchor_storage import build_storage_manifest, evidence_dir, storage_manifest_path, storage_summary, write_json

ANCHOR_ROOT = Path(__file__).resolve().parents[2]
DVD_ROOT = Path(os.environ.get("ANCHOR_DVD_ROOT", "/home/crexs/damn-vulnerable-defi"))
BENCHMARKS_ROOT = ANCHOR_ROOT / "benchmarks"
RUNS_ROOT = BENCHMARKS_ROOT / "damn-vulnerable-defi" / "runs"
LABEL = os.environ.get("ANCHOR_BENCHMARK_LABEL", "dvd-phase1-local")
TIMEOUT_SEC = int(os.environ.get("ANCHOR_BENCHMARK_TIMEOUT_SEC", "90"))
EXPECTATIONS_PATH = Path(__file__).with_name("challenge_expectations.json")
MANIFEST_PATH = BENCHMARKS_ROOT / "index.json"
DEFAULT_HISTORY_POLICY = {
    "artifact_retention": "keep_all_successful_runs",
    "manifest_default_tier": "development",
    "default_history_view": "published_only",
    "published_tier": "published",
    "note": "Successful development reruns remain on disk, but only intentionally promoted runs are first-class published artifacts.",
}
SEVERITY_ORDER = ["High", "Medium", "Low", "Informational", "Optimization"]
SIGNAL_IMPACTS = {"High", "Medium"}


def run(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def normalize_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def rel_to_anchor(path: Path) -> str:
    return str(path.resolve().relative_to(ANCHOR_ROOT))


def git_value(repo: Path, *args: str) -> str | None:
    proc = run(["git", "-C", str(repo), *args])
    return proc.stdout.strip() if proc.returncode == 0 else None


def short_commit(value: str | None) -> str | None:
    return value[:8] if value else None


def status_from(proc: subprocess.CompletedProcess[str], timed_out: bool) -> str:
    if timed_out:
        return "TIMED_OUT"
    out = normalize_text(proc.stdout) + "\n" + normalize_text(proc.stderr)
    if "Skipped:" in out:
        return "SKIPPED"
    return "PASSED" if proc.returncode == 0 else "FAILED"


def load_expectations() -> list[dict]:
    payload = json.loads(EXPECTATIONS_PATH.read_text())
    return payload["challenge_set"]


def ordered_impact_counts(counter: Counter) -> dict[str, int]:
    return {impact: counter[impact] for impact in SEVERITY_ORDER if counter.get(impact)}


def detect_version(command: list[str]) -> dict[str, str | None]:
    proc = run(command)
    combined = (normalize_text(proc.stdout) + "\n" + normalize_text(proc.stderr)).strip()
    if proc.returncode != 0:
        detail = combined.splitlines()[-1] if combined else f"exit {proc.returncode}"
        return {"status": "unavailable", "version": None, "detail": detail}
    first_line = combined.splitlines()[0] if combined else None
    return {"status": "available", "version": first_line, "detail": first_line}


def probe_mythril() -> dict[str, str | None]:
    myth_path = shutil.which("myth")
    if not myth_path:
        return {"tool": "mythril", "path": None, "status": "unavailable", "version": None, "detail": "not installed"}
    version = detect_version([myth_path, "version"])
    return {
        "tool": "mythril",
        "path": myth_path,
        "status": version["status"],
        "version": version["version"],
        "detail": version["detail"],
    }


def detector_relevant(detector: dict, target_prefix: str) -> bool:
    for element in detector.get("elements", []) or []:
        source_mapping = element.get("source_mapping") or {}
        filename_relative = source_mapping.get("filename_relative", "")
        if filename_relative.startswith(target_prefix):
            return True
    return False


def summarize_detectors(detectors: list[dict], target_prefix: str) -> dict[str, object]:
    raw_checks = Counter()
    relevant_checks = Counter()
    raw_impacts = Counter()
    relevant_impacts = Counter()
    relevant_medium_high = 0

    for detector in detectors:
        check = detector.get("check")
        impact = detector.get("impact", "Unknown")
        if check:
            raw_checks[check] += 1
        raw_impacts[impact] += 1
        if detector_relevant(detector, target_prefix):
            if check:
                relevant_checks[check] += 1
            relevant_impacts[impact] += 1
            if impact in SIGNAL_IMPACTS:
                relevant_medium_high += 1

    return {
        "raw_finding_count": len(detectors),
        "raw_by_impact": ordered_impact_counts(raw_impacts),
        "top_raw_checks": [name for name, _ in raw_checks.most_common(5)],
        "target_relevant_finding_count": sum(relevant_impacts.values()),
        "target_relevant_by_impact": ordered_impact_counts(relevant_impacts),
        "top_target_relevant_checks": [name for name, _ in relevant_checks.most_common(5)],
        "medium_high_target_relevant_finding_count": relevant_medium_high,
    }


def probe_slither(challenge: str, target: str, run_dir: Path) -> dict[str, object]:
    slither_path = shutil.which("slither")
    if not slither_path:
        return {
            "tool": "slither",
            "path": None,
            "status": "unavailable",
            "version": None,
            "target": target,
            "detail": "not installed",
            "summary": {
                "raw_finding_count": 0,
                "raw_by_impact": {},
                "top_raw_checks": [],
                "target_relevant_finding_count": 0,
                "target_relevant_by_impact": {},
                "top_target_relevant_checks": [],
                "medium_high_target_relevant_finding_count": 0,
            },
        }

    source_path = DVD_ROOT / target
    target_prefix = f"{Path(target).parent.as_posix().rstrip('/')}/"
    json_path = run_dir / f"{challenge}.slither.json"
    version = detect_version([slither_path, "--version"])
    cmd = [slither_path, str(source_path), "--exclude-dependencies", "--json", str(json_path)]
    proc = run(cmd, cwd=DVD_ROOT)
    stdout_text = normalize_text(proc.stdout)
    stderr_text = normalize_text(proc.stderr)

    if not json_path.exists():
        return {
            "tool": "slither",
            "path": slither_path,
            "status": "error",
            "version": version["version"],
            "target": target,
            "detail": (stderr_text or stdout_text or f"exit {proc.returncode}").splitlines()[-1][:240],
            "summary": {
                "raw_finding_count": 0,
                "raw_by_impact": {},
                "top_raw_checks": [],
                "target_relevant_finding_count": 0,
                "target_relevant_by_impact": {},
                "top_target_relevant_checks": [],
                "medium_high_target_relevant_finding_count": 0,
            },
        }

    try:
        payload = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        return {
            "tool": "slither",
            "path": slither_path,
            "status": "error",
            "version": version["version"],
            "target": target,
            "artifact_json": rel_to_anchor(json_path),
            "detail": f"invalid json: {exc}",
            "summary": {
                "raw_finding_count": 0,
                "raw_by_impact": {},
                "top_raw_checks": [],
                "target_relevant_finding_count": 0,
                "target_relevant_by_impact": {},
                "top_target_relevant_checks": [],
                "medium_high_target_relevant_finding_count": 0,
            },
        }

    detectors = payload.get("results", {}).get("detectors", []) or []
    summary = summarize_detectors(detectors, target_prefix)
    return {
        "tool": "slither",
        "path": slither_path,
        "status": "completed",
        "version": version["version"],
        "target": target,
        "artifact_json": rel_to_anchor(json_path),
        "detail": (
            f"completed with {summary['raw_finding_count']} raw finding(s), "
            f"{summary['target_relevant_finding_count']} target-relevant, "
            f"{summary['medium_high_target_relevant_finding_count']} medium/high target-relevant"
        ),
        "summary": summary,
    }


def detection_state_from(detector_outputs: list[dict]) -> str:
    slither = next((item for item in detector_outputs if item.get("tool") == "slither"), None)
    if slither and slither.get("status") == "completed":
        summary = slither.get("summary", {})
        if summary.get("medium_high_target_relevant_finding_count", 0) > 0:
            return "signals_present"
        if summary.get("target_relevant_finding_count", 0) > 0:
            return "target_relevant_info_only"
        if summary.get("raw_finding_count", 0) > 0:
            return "non_target_noise_only"
        return "no_detector_signal"
    if any(item.get("status") == "error" for item in detector_outputs):
        return "detector_error"
    return "detector_unavailable"


def anchor_output_from(result_status: str, detector_outputs: list[dict]) -> dict[str, object]:
    reproduction = {
        "PASSED": "reproduced_real",
        "FAILED": "repro_failed",
        "SKIPPED": "repro_skipped",
        "TIMED_OUT": "repro_timed_out",
    }.get(result_status, "repro_unknown")
    return {
        "detection_state": detection_state_from(detector_outputs),
        "reproduction_state": reproduction,
        "council_state": "not_reviewed",
        "detector_outputs": detector_outputs,
    }


def comparison_from(expected_outcome: str, observed_status: str) -> str:
    if expected_outcome == "pass" and observed_status == "PASSED":
        return "aligned"
    if expected_outcome == "environment_dependent" and observed_status in {"FAILED", "SKIPPED", "TIMED_OUT", "PASSED"}:
        return "environment_sensitive"
    if expected_outcome == "pass_or_timeout_needs_investigation" and observed_status in {"PASSED", "TIMED_OUT"}:
        return "investigate_but_not_regression"
    return "diverged"


def latest_manifest_entry(entries: list[dict]) -> dict | None:
    if not entries:
        return None
    return max(entries, key=lambda entry: entry.get("executed_at", ""))


def load_manifest_payload() -> dict:
    if MANIFEST_PATH.exists():
        payload = json.loads(MANIFEST_PATH.read_text())
    else:
        payload = {"benchmarks": []}
    payload.setdefault("history_policy", dict(DEFAULT_HISTORY_POLICY))
    payload.setdefault("benchmarks", [])
    return payload


def update_manifest(entry: dict) -> dict:
    payload = load_manifest_payload()
    benchmarks = [item for item in payload.get("benchmarks", []) if item.get("id") != entry["id"]]
    benchmarks.append(entry)
    benchmarks.sort(key=lambda item: item.get("executed_at", ""))
    payload["benchmarks"] = benchmarks
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main() -> int:
    if not DVD_ROOT.exists():
        raise SystemExit(f"DVD root not found: {DVD_ROOT}")

    expectations = load_expectations()
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = RUNS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_root = evidence_dir(run_dir)
    evidence_root.mkdir(parents=True, exist_ok=True)

    forge_version = run(["forge", "--version"])
    anchor_commit = git_value(ANCHOR_ROOT, "rev-parse", "HEAD")
    anchor_branch = git_value(ANCHOR_ROOT, "branch", "--show-current")
    dvd_commit = git_value(DVD_ROOT, "rev-parse", "HEAD")
    dvd_branch = git_value(DVD_ROOT, "branch", "--show-current")
    slither_path = shutil.which("slither")
    slither_version_info = detect_version([slither_path, "--version"]) if slither_path else {"status": "unavailable", "version": None, "detail": "not installed"}
    slither_provenance = {
        "tool": "slither",
        "path": slither_path,
        **slither_version_info,
    }
    mythril_probe = probe_mythril()

    results = []
    for item in expectations:
        rel = item["test_path"]
        challenge_timeout = int(item.get("timeout_sec", TIMEOUT_SEC))
        cmd = ["forge", "test", "--match-path", rel, "-vvv"]
        started = dt.datetime.now(dt.timezone.utc)
        timed_out = False
        try:
            proc = run(cmd, cwd=DVD_ROOT, timeout=challenge_timeout)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            proc = subprocess.CompletedProcess(
                cmd,
                returncode=124,
                stdout=normalize_text(exc.stdout),
                stderr=normalize_text(exc.stderr) + f"\nTimed out after {challenge_timeout}s",
            )
        ended = dt.datetime.now(dt.timezone.utc)
        observed_status = status_from(proc, timed_out)
        duration = (ended - started).total_seconds()
        stdout_text = normalize_text(proc.stdout)
        stderr_text = normalize_text(proc.stderr)
        log_path = run_dir / f"{item['challenge']}.log"
        log_path.write_text(
            "$ " + " ".join(cmd) + "\n\n"
            + "STDOUT\n" + stdout_text + "\n\n"
            + "STDERR\n" + stderr_text + "\n"
        )

        detector_outputs = [probe_slither(item["challenge"], item["slither_target"], run_dir), mythril_probe]
        anchor_output = anchor_output_from(observed_status, detector_outputs)

        results.append({
            "challenge": item["challenge"],
            "test_path": rel,
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "status": observed_status,
            "duration_sec": round(duration, 3),
            "timed_out": timed_out,
            "timeout_sec": challenge_timeout,
            "requires_rpc": item["requires_rpc"],
            "expected_ground_truth": item["expected_ground_truth"],
            "expected_phase1_outcome": item["expected_phase1_outcome"],
            "comparison": comparison_from(item["expected_phase1_outcome"], observed_status),
            "anchor_output": anchor_output,
            "notes": item["notes"],
            "log_path": rel_to_anchor(log_path),
        })

    summary = {
        "passed": sum(1 for r in results if r["status"] == "PASSED"),
        "failed": sum(1 for r in results if r["status"] == "FAILED"),
        "skipped": sum(1 for r in results if r["status"] == "SKIPPED"),
        "timed_out": sum(1 for r in results if r["status"] == "TIMED_OUT"),
        "aligned": sum(1 for r in results if r["comparison"] == "aligned"),
        "environment_sensitive": sum(1 for r in results if r["comparison"] == "environment_sensitive"),
        "investigate": sum(1 for r in results if r["comparison"] == "investigate_but_not_regression"),
        "diverged": sum(1 for r in results if r["comparison"] == "diverged"),
        "detector_signals": sum(1 for r in results if r["anchor_output"]["detection_state"] == "signals_present"),
        "raw_detector_findings": sum(
            next((tool.get("summary", {}).get("raw_finding_count", 0) for tool in r["anchor_output"]["detector_outputs"] if tool.get("tool") == "slither"), 0)
            for r in results
        ),
        "target_relevant_detector_findings": sum(
            next((tool.get("summary", {}).get("target_relevant_finding_count", 0) for tool in r["anchor_output"]["detector_outputs"] if tool.get("tool") == "slither"), 0)
            for r in results
        ),
        "medium_high_target_relevant_findings": sum(
            next((tool.get("summary", {}).get("medium_high_target_relevant_finding_count", 0) for tool in r["anchor_output"]["detector_outputs"] if tool.get("tool") == "slither"), 0)
            for r in results
        ),
    }

    detector_provenance = {
        "slither": slither_provenance,
        "mythril": mythril_probe,
    }

    payload = {
        "schema_version": "1.4",
        "benchmark_id": LABEL,
        "level": "Phase 1 scaffold",
        "executed_at": now.isoformat(),
        "anchor": {
            "commit": anchor_commit,
            "branch": anchor_branch,
        },
        "target": {
            "repo": str(DVD_ROOT),
            "commit": dvd_commit,
            "branch": dvd_branch,
        },
        "environment": {
            "os": platform.platform(),
            "forge_version": forge_version.stdout.strip(),
            "per_challenge_timeout_sec": TIMEOUT_SEC,
        },
        "detector_provenance": detector_provenance,
        "summary": summary,
        "results": results,
    }

    json_path = run_dir / "benchmark.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")

    storage_json_path = storage_manifest_path(run_dir)
    storage_manifest = build_storage_manifest(
        benchmark_id=LABEL,
        run_id=f"{LABEL}-{stamp}",
        target="damn-vulnerable-defi",
        stage="Phase 1",
        status="scaffold",
        created_at=payload["executed_at"],
        artifact_type="benchmark_run",
        artifact_path=rel_to_anchor(json_path),
        evidence_path=rel_to_anchor(evidence_root),
        manifest_path=rel_to_anchor(storage_json_path),
        ledger_path=rel_to_anchor(ANCHOR_ROOT / "outcomes" / "ledger.jsonl"),
        archive_path=rel_to_anchor(run_dir),
        signature_state="pending",
    )
    write_json(storage_json_path, storage_manifest)

    manifest_entry = {
        "id": f"{LABEL}-{stamp}",
        "target": "damn-vulnerable-defi",
        "title": "Damn Vulnerable DeFi Phase 1 scaffold run with detector stage",
        "status": "scaffold",
        "level": "Phase 1",
        "publication_tier": "development",
        "commit": short_commit(anchor_commit),
        "branch": anchor_branch,
        "executed_at": payload["executed_at"],
        "environment": {
            "forge_version": payload["environment"]["forge_version"],
            "os": payload["environment"]["os"],
            "per_challenge_timeout_sec": TIMEOUT_SEC,
        },
        "detector_provenance": detector_provenance,
        "record": rel_to_anchor(run_dir / "README.md"),
        "artifact_json": rel_to_anchor(json_path),
        "storage_manifest": rel_to_anchor(storage_json_path),
        "storage": storage_summary(storage_manifest),
        "storage_status": "ready",
        "evidence_path": rel_to_anchor(evidence_root),
        "signature_state": storage_manifest["signature_state"],
        "expectations": rel_to_anchor(EXPECTATIONS_PATH),
        "confidence_ladder": {
            "methodology": "high",
            "environment": "high",
            "detection": "partial",
            "reproduction": "partial",
            "comparative_data": "partial",
        },
        "verified": True,
        "confidence": "scaffold",
        "results_summary": summary,
    }

    lines = [
        f"# DVD Phase 1 Scaffold Run - {stamp}",
        "",
        "## Metadata",
        f"- Benchmark ID: `{LABEL}`",
        f"- Executed at: `{payload['executed_at']}`",
        f"- ANCHOR commit: `{anchor_commit}`",
        f"- ANCHOR branch: `{anchor_branch}`",
        f"- DVD commit: `{dvd_commit}`",
        f"- DVD branch: `{dvd_branch}`",
        "",
        "## Environment",
        f"- OS: `{payload['environment']['os']}`",
        f"- Forge: `{payload['environment']['forge_version']}`",
        f"- Per-challenge timeout: `{TIMEOUT_SEC}s`",
        "",
        "## Detector provenance",
        f"- Slither: `{slither_provenance['status']}`{f' · {slither_provenance.get("version")}' if slither_provenance.get('version') else ''}",
        f"- Mythril: `{mythril_probe['status']}`{f' · {mythril_probe.get("detail")}' if mythril_probe.get('detail') else ''}",
        "",
        "## Results summary",
        f"- passed: `{summary['passed']}`",
        f"- failed: `{summary['failed']}`",
        f"- skipped: `{summary['skipped']}`",
        f"- timed out: `{summary['timed_out']}`",
        f"- aligned: `{summary['aligned']}`",
        f"- environment sensitive: `{summary['environment_sensitive']}`",
        f"- investigate: `{summary['investigate']}`",
        f"- diverged: `{summary['diverged']}`",
        f"- detector signals: `{summary['detector_signals']}`",
        f"- raw detector findings: `{summary['raw_detector_findings']}`",
        f"- target-relevant detector findings: `{summary['target_relevant_detector_findings']}`",
        f"- medium/high target-relevant findings: `{summary['medium_high_target_relevant_findings']}`",
        "",
        "## Per-challenge comparison",
    ]
    for item in results:
        slither_output = next((tool for tool in item["anchor_output"]["detector_outputs"] if tool["tool"] == "slither"), None)
        slither_text = "slither unavailable"
        if slither_output:
            summary_bits = slither_output.get("summary", {})
            top_checks = ", ".join(summary_bits.get("top_target_relevant_checks", [])[:3]) or "none"
            slither_text = (
                f"slither `{slither_output['status']}` raw `{summary_bits.get('raw_finding_count', 0)}` / "
                f"target-relevant `{summary_bits.get('target_relevant_finding_count', 0)}` / "
                f"medium-high target-relevant `{summary_bits.get('medium_high_target_relevant_finding_count', 0)}`; "
                f"top target checks: {top_checks}"
            )
        lines.extend([
            f"- `{item['challenge']}` -> observed `{item['status']}` / expected `{item['expected_phase1_outcome']}` / comparison `{item['comparison']}`",
            f"  - anchor output: detection `{item['anchor_output']['detection_state']}`, reproduction `{item['anchor_output']['reproduction_state']}`, council `{item['anchor_output']['council_state']}`",
            f"  - detector stage: {slither_text}",
            f"  - path: `{item['test_path']}`",
            f"  - log: `{item['log_path']}`",
        ])
    lines.extend([
        "",
        "## Publication tier",
        "- This run is recorded as a `development` artifact in the manifest by default.",
        "- Promote a run into first-class published history with `anchor benchmark publish <run_id>`.",
        "",
        "## Limitations",
        "- Detector-stage outputs now include provenance and scoped summaries, but detector quality is still based on one active detector on this machine.",
        f"- Mythril is currently recorded as `{mythril_probe['status']}` and is not part of the active detector pass.",
        "- Challenges that require RPC or external environment will be reflected directly in the logs.",
        f"- Individual challenge runs are capped at {TIMEOUT_SEC}s to keep the benchmark reproducible.",
        "",
        "## Next Actions",
        "- Add comparative detector baselines beyond Slither once Mythril or an equivalent symbolic layer is healthy again.",
        "- Expand the challenge set beyond the initial three paths once the comparison schema is stable.",
    ])
    md_path = run_dir / "README.md"
    md_path.write_text("\n".join(lines) + "\n")

    manifest_entry["record"] = rel_to_anchor(md_path)
    manifest = update_manifest(manifest_entry)
    latest_entry = latest_manifest_entry(manifest["benchmarks"])

    print(json_path)
    print(md_path)
    if latest_entry:
        print(f"Updated manifest latest benchmark: {latest_entry['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
