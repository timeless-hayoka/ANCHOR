#!/usr/bin/env python3
"""Produce a bounded review-only diff of pinned and Sourcify-verified source.

This tool makes read-only HTTPS requests; it never connects to chain RPCs,
broadcasts transactions, or infers vulnerabilities from source deltas.
"""
from __future__ import annotations

import argparse
import difflib
import json
import urllib.error
import urllib.request
from pathlib import Path

ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
CHAIN_ID = "10"
URL = f"https://sourcify.dev/server/v2/contract/{CHAIN_ID}/{ADDRESS}?fields=all"


def bounded_hunks(local: str, verified: str, *, max_hunks: int = 24, max_lines: int = 24) -> dict:
    """Extract concise, auditable changed lines (never claims semantic equivalence)."""
    left, right = local.splitlines(), verified.splitlines()
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    changes = []
    for kind, i1, i2, j1, j2 in matcher.get_opcodes():
        if kind == "equal":
            continue
        before = left[i1:i2]
        after = right[j1:j2]
        changes.append({
            "kind": kind,
            "local_lines": [i1 + 1, i2],
            "verified_lines": [j1 + 1, j2],
            "local_excerpt": [s[:200] for s in before[:max_lines]],
            "verified_excerpt": [s[:200] for s in after[:max_lines]],
            "truncated": len(before) > max_lines or len(after) > max_lines,
        })
    return {
        "state": "SOURCE_DELTA_REVIEW_ONLY",
        "hunk_count": len(changes),
        "hunks": changes[:max_hunks],
        "hunks_truncated": len(changes) > max_hunks,
        "conclusion": "No security impact or runtime-bytecode equivalence established",
    }


def analyze(local: str, snapshot: object) -> dict:
    if not isinstance(snapshot, dict):
        return {"state": "UNVERIFIED", "reason": "invalid metadata"}
    if str(snapshot.get("chainId")) != CHAIN_ID or str(snapshot.get("address", "")).lower() != ADDRESS:
        return {"state": "UNVERIFIED", "reason": "chain or address mismatch"}
    match = snapshot.get("runtimeMatch")
    if match not in ("match", "exact_match"):
        return {"state": "UNVERIFIED", "reason": "Sourcify runtime source not verified"}
    sources = snapshot.get("sources")
    if not isinstance(sources, dict):
        return {"state": "UNVERIFIED", "reason": "missing sources"}
    found = [
        (path, item.get("content") if isinstance(item, dict) else item)
        for path, item in sources.items()
        if isinstance(path, str) and path.rsplit("/", 1)[-1] == "LendingPool.sol"
    ]
    if len(found) != 1 or not isinstance(found[0][1], str):
        return {"state": "UNVERIFIED", "reason": "ambiguous or absent verified LendingPool.sol"}
    path, verified = found[0]
    report = bounded_hunks(local, verified)
    report.update({
        "chain_id": CHAIN_ID,
        "address": ADDRESS,
        "verified_path": path,
        "sourcify_runtime_match": match,
        "same_source_text": local == verified,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, help="Saved Sourcify JSON for offline checks")
    args = parser.parse_args()
    try:
        local = args.source.read_text(encoding="utf-8")
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        else:
            request = urllib.request.Request(
                URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-source-review"}
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read(6_000_001)
            if len(raw) > 6_000_000:
                raise ValueError("metadata exceeds bound")
            snapshot = json.loads(raw.decode("utf-8"))
        report = analyze(local, snapshot)
    except (OSError, ValueError, UnicodeError, urllib.error.URLError) as exc:
        report = {"state": "UNVERIFIED", "reason": type(exc).__name__}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("state") == "SOURCE_DELTA_REVIEW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
