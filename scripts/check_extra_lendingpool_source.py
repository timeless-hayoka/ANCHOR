#!/usr/bin/env python3
"""Read-only, fail-closed source comparison for the Extra Finance LendingPool.

This is NOT a reproduction, eligibility check, or a whole-contract bytecode
equivalence proof. It compares one pinned Solidity source file to Sourcify's
independently verified source listing at a chain-specific address.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CHAIN_ID = "10"
ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
SOURCE_NAME = "LendingPool.sol"
API_URL = f"https://sourcify.dev/server/v2/contract/{CHAIN_ID}/{ADDRESS}?fields=all"


def analyze_snapshot(snapshot: Any, source_text: str) -> dict[str, Any]:
    """No network; return a conservative verification result."""
    result: dict[str, Any] = {
        "chain_id": CHAIN_ID,
        "address": ADDRESS,
        "source_file": SOURCE_NAME,
        "status": "NOT_VERIFIED",
        "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "matched_source_paths": [],
        "reason": "",
    }
    if not isinstance(snapshot, dict):
        result["reason"] = "snapshot is not a JSON object"
        return result
    if str(snapshot.get("chainId", "")) != CHAIN_ID:
        result["reason"] = "snapshot chain ID mismatch"
        return result
    if str(snapshot.get("address", "")).lower() != ADDRESS:
        result["reason"] = "snapshot address mismatch"
        return result
    runtime_match = snapshot.get("runtimeMatch")
    result["reported_runtime_match"] = runtime_match if isinstance(runtime_match, str) else None
    if runtime_match not in {"exact_match", "match"}:
        result["reason"] = "Sourcify runtime verification not established"
        return result
    sources = snapshot.get("sources")
    if not isinstance(sources, dict) or not sources:
        result["reason"] = "verified source listing unavailable"
        return result

    possible = []
    for path, entry in sources.items():
        if not isinstance(path, str) or path.rsplit("/", 1)[-1] != SOURCE_NAME:
            continue
        text = entry.get("content") if isinstance(entry, dict) else entry
        if isinstance(text, str):
            possible.append((path, text))

    if not possible:
        result["reason"] = "verified LendingPool.sol content unavailable"
        return result
    matched = [path for path, text in possible if text == source_text]
    if not matched:
        result["reason"] = "verified LendingPool.sol text differs from local source"
        return result

    # Match of a single file plus the explorer's exact-runtime verification
    # is useful, but not proof of full repository/build equivalence.
    result["status"] = (
        "PINNED_SOURCE_MATCH"
        if runtime_match == "exact_match"
        else "PINNED_SOURCE_MATCH_NONEXACT_RUNTIME"
    )
    result["matched_source_paths"] = sorted(matched)
    result["reason"] = (
        "single source file agrees with Sourcify's runtime-verified source; "
        + ("runtime verification is exact; " if runtime_match == "exact_match"
           else "runtime verification is non-exact; ")
        + "full compilation inputs, libraries, immutables and onchain bytecode "
        "still require independent comparison"
    )
    return result


def load_snapshot(path: Path | None) -> Any:
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        API_URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-readonly-verifier"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        # Bound external data before parsing.
        raw = response.read(6_000_001)
    if len(raw) > 6_000_000:
        raise ValueError("Sourcify response exceeds size limit")
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Pinned local LendingPool.sol")
    parser.add_argument("--snapshot", type=Path, help="Offline Sourcify v2 API JSON (omit to fetch read-only)")
    args = parser.parse_args(argv)

    try:
        source_text = args.source.read_text(encoding="utf-8")
        snapshot = load_snapshot(args.snapshot)
        outcome = analyze_snapshot(snapshot, source_text)
    except (OSError, ValueError, UnicodeError, urllib.error.URLError) as exc:
        outcome = {
            "status": "NOT_VERIFIED",
            "chain_id": CHAIN_ID,
            "address": ADDRESS,
            "reason": f"verification unavailable: {type(exc).__name__}",
        }
    print(json.dumps(outcome, indent=2, sort_keys=True))
    # Exit 3 conveys source-text agreement with non-exact runtime evidence,
    # never the stronger exact-runtime status. Missing/mismatch stays exit 2.
    return {"PINNED_SOURCE_MATCH": 0, "PINNED_SOURCE_MATCH_NONEXACT_RUNTIME": 3}.get(outcome["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
