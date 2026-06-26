#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import subprocess
from pathlib import Path

ANCHOR_ROOT = Path(__file__).resolve().parents[2]
DVD_ROOT = Path(os.environ.get("ANCHOR_DVD_ROOT", "/home/crexs/damn-vulnerable-defi"))
LABEL = os.environ.get("ANCHOR_BENCHMARK_LABEL", "dvd-phase1-local")
TIMEOUT_SEC = int(os.environ.get("ANCHOR_BENCHMARK_TIMEOUT_SEC", "90"))
CHALLENGES = [
    "test/shards/Shards.t.sol",
    "test/wallet-mining/WalletMining.t.sol",
    "test/withdrawal/Withdrawal.t.sol",
]


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


def git_value(repo: Path, *args: str) -> str | None:
    proc = run(["git", "-C", str(repo), *args])
    return proc.stdout.strip() if proc.returncode == 0 else None


def status_from(proc: subprocess.CompletedProcess[str], timed_out: bool) -> str:
    if timed_out:
        return "TIMED_OUT"
    out = normalize_text(proc.stdout) + "\n" + normalize_text(proc.stderr)
    if "Skipped:" in out:
        return "SKIPPED"
    return "PASSED" if proc.returncode == 0 else "FAILED"


def main() -> int:
    if not DVD_ROOT.exists():
        raise SystemExit(f"DVD root not found: {DVD_ROOT}")

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = ANCHOR_ROOT / "benchmarks" / "damn-vulnerable-defi" / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    forge_version = run(["forge", "--version"])
    anchor_commit = git_value(ANCHOR_ROOT, "rev-parse", "HEAD")
    anchor_branch = git_value(ANCHOR_ROOT, "branch", "--show-current")
    dvd_commit = git_value(DVD_ROOT, "rev-parse", "HEAD")
    dvd_branch = git_value(DVD_ROOT, "branch", "--show-current")

    results = []
    for rel in CHALLENGES:
        cmd = ["forge", "test", "--match-path", rel, "-vvv"]
        started = dt.datetime.now(dt.timezone.utc)
        timed_out = False
        try:
            proc = run(cmd, cwd=DVD_ROOT, timeout=TIMEOUT_SEC)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            proc = subprocess.CompletedProcess(
                cmd,
                returncode=124,
                stdout=normalize_text(exc.stdout),
                stderr=normalize_text(exc.stderr) + f"\nTimed out after {TIMEOUT_SEC}s",
            )
        ended = dt.datetime.now(dt.timezone.utc)
        duration = (ended - started).total_seconds()
        name = Path(rel).parent.name
        stdout_text = normalize_text(proc.stdout)
        stderr_text = normalize_text(proc.stderr)
        log_path = run_dir / f"{name}.log"
        log_path.write_text(
            "$ " + " ".join(cmd) + "\n\n"
            + "STDOUT\n" + stdout_text + "\n\n"
            + "STDERR\n" + stderr_text + "\n"
        )
        results.append({
            "challenge": name,
            "test_path": rel,
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "status": status_from(proc, timed_out),
            "duration_sec": round(duration, 3),
            "timed_out": timed_out,
            "log_path": str(log_path.relative_to(ANCHOR_ROOT)),
        })

    payload = {
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
        "results": results,
    }

    json_path = run_dir / "benchmark.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")

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
        "## Results",
    ]
    for item in results:
        lines.extend([
            f"- `{item['challenge']}` -> `{item['status']}` in `{item['duration_sec']}`s (rc `{item['returncode']}`)",
            f"  - path: `{item['test_path']}`",
            f"  - log: `{item['log_path']}`",
        ])
    lines.extend([
        "",
        "## Limitations",
        "- This scaffold records execution outcomes, not ANCHOR detector metrics yet.",
        "- Challenges that require RPC or external environment will be reflected directly in the logs.",
        f"- Individual challenge runs are capped at {TIMEOUT_SEC}s to keep the benchmark reproducible.",
        "",
        "## Next Actions",
        "- Add expected challenge labels and ANCHOR detection outputs.",
        "- Convert the scaffold into a benchmark that publishes automated detection metrics.",
    ])
    md_path = run_dir / "README.md"
    md_path.write_text("\n".join(lines) + "\n")

    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
