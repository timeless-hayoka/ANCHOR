"""Offline, read-only npm release integrity heuristics. No artifact execution."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DANGEROUS_HOOKS = ("preinstall", "install", "postinstall")
NETWORK_TERMS = ("curl ", "wget ", "http://", "https://", "fetch(")
EXEC_TERMS = ("node -e", "bash ", "sh ", "powershell", "child_process", "exec(")
PIPE_TO_SHELL = re.compile(r"\|\s*(?:sh|bash|zsh)(?:\s|$|[;&|])", re.IGNORECASE)


def inspect_package(package: dict, *, approved_commit: str | None = None) -> list[dict]:
    """Return evidence-backed indicators; no single indicator proves compromise."""
    if not isinstance(package, dict):
        raise ValueError("package metadata must be an object")
    findings = []
    scripts = package.get("scripts", {})
    if not isinstance(scripts, dict):
        findings.append({"rule": "INVALID_SCRIPTS", "severity": "medium", "evidence": "scripts is not an object"})
        scripts = {}
    for hook in DANGEROUS_HOOKS:
        command = scripts.get(hook)
        if not isinstance(command, str):
            continue
        findings.append({"rule": "INSTALL_HOOK", "severity": "info", "evidence": hook})
        lowered = command.lower()
        if any(term in lowered for term in NETWORK_TERMS):
            findings.append({"rule": "INSTALL_NETWORK", "severity": "high", "evidence": hook})
        if any(term in lowered for term in EXEC_TERMS) or PIPE_TO_SHELL.search(command):
            findings.append({"rule": "INSTALL_EXECUTION", "severity": "medium", "evidence": hook})
    provenance = package.get("provenance", {})
    if approved_commit is not None:
        actual = provenance.get("source_commit") if isinstance(provenance, dict) else None
        if actual != approved_commit:
            findings.append({"rule": "UNAPPROVED_SOURCE_COMMIT", "severity": "high",
                             "evidence": {"expected": approved_commit, "actual": actual}})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local npm metadata without executing code")
    parser.add_argument("metadata", type=Path, help="Local JSON metadata file")
    parser.add_argument("--approved-commit", help="Previously reviewed commit SHA")
    args = parser.parse_args()
    data = json.loads(args.metadata.read_text(encoding="utf-8"))
    findings = inspect_package(data, approved_commit=args.approved_commit)
    print(json.dumps({"schema_version": 1, "findings": findings}, indent=2))
    return 1 if any(f["severity"] == "high" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
