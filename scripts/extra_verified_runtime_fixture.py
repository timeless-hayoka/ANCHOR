#!/usr/bin/env python3
"""Prepare a strictly validated, local-only Foundry runtime smoke-test fixture.

No RPC writes, deployments or real-protocol transactions. Uses read-only
Sourcify metadata and an independent eth_getCode digest report.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from extra_runtime_transform_reconciliation import (
    ADDRESS, CHAIN_ID, URL, examine, hex_bytes, sha,
)

EXPECTED_DECLARATION = re.compile(
    r"\baddress\s+public\s+immutable\s+addressRegistry\b"
)


def fixture(snapshot: Any, rpc_evidence: Any) -> dict[str, str]:
    result = examine(snapshot, rpc_evidence)
    if result["state"] != "DECLARED_TRANSFORMS_RECONCILED":
        raise ValueError("runtime transformation evidence not reconciled")
    source = snapshot.get("sources", {}).get("contracts/lendingpool/LendingPool.sol")
    text = source.get("content") if isinstance(source, dict) else None
    if not isinstance(text, str) or not EXPECTED_DECLARATION.search(text):
        raise ValueError("verified source lacks expected immutable addressRegistry")
    rt = snapshot["runtimeBytecode"]
    immutables = [
        item for item in rt["transformations"]
        if item["reason"] == "immutable"
    ]
    if not immutables or any(item.get("type") != "replace" for item in immutables):
        raise ValueError("missing immutable reference transformations")
    ids = {item.get("id") for item in immutables}
    values = rt.get("transformationValues", {}).get("immutables")
    if len(ids) != 1 or not isinstance(values, dict):
        raise ValueError("cannot map immutable to one deterministic registry value")
    identity = next(iter(ids))
    raw = hex_bytes(values.get(identity))
    if len(raw) != 32 or raw[:12] != bytes(12) or raw[12:] == bytes(20):
        raise ValueError("immutable is not a canonical nonzero Solidity address")
    # All instances of this immutable are already reference-map checked by
    # examine(). Validate the number of referenced spans as a final guard.
    refs = rt.get("immutableReferences", {}).get(identity)
    if not isinstance(refs, list) or len(refs) != len(immutables):
        raise ValueError("immutable reference count is inconsistent")
    return {
        "runtime_hex": rt["onchainBytecode"].lower(),
        "registry_address": "0x" + raw[12:].hex(),
        "target_address": ADDRESS,
        "chain_id": CHAIN_ID,
        "evidence_class": "LOCAL_EVM_RUNTIME_SMOKE_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-evidence", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-runtime-lab-fixture"}
            ), timeout=20,
        ) as response:
            raw = response.read(6_000_001)
        if len(raw) > 6_000_000:
            raise ValueError("Sourcify response exceeds limit")
        snap = json.loads(raw.decode("utf-8"))
        rpc = json.loads(args.rpc_evidence.read_text(encoding="utf-8"))
        data = fixture(snap, rpc)
        args.outdir.mkdir(parents=True, exist_ok=True)
        # The runtime is public code. Separate from concise evidence so CI
        # doesn't log the full bytecode string by accident.
        (args.outdir / "runtime.hex").write_text(data.pop("runtime_hex"), encoding="utf-8")
        (args.outdir / "fixture.json").write_text(
            json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(data, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, UnicodeError) as exc:
        print(json.dumps({"state": "LOCAL_FIXTURE_NOT_PROVEN", "reason": str(exc)[:180]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
