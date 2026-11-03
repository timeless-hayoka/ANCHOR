#!/usr/bin/env python3
"""Prepare a strictly validated, local-only Foundry runtime smoke-test fixture.

No RPC writes, deployments or real-protocol transactions. Uses read-only
Sourcify metadata and an independent eth_getCode digest report.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from extra_verified_source_compile import prepare_input

from extra_runtime_transform_reconciliation import (
    ADDRESS, CHAIN_ID, URL, examine, hex_bytes, sha,
)

EXPECTED_DECLARATION = re.compile(
    r"\baddress\s+public\s+immutable\s+addressRegistry\b"
)


def compile_verified_ast(snapshot: Any) -> dict[str, Any]:
    """Compile only the AST from the same 0.8.18 Standard JSON source input."""
    standard, _ = prepare_input(snapshot)
    standard["settings"]["outputSelection"] = {
        "contracts/lendingpool/LendingPool.sol": {"": ["ast"]},
    }
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as infile:
        json.dump(standard, infile)
        infile.flush()
        infile.seek(0)
        proc = subprocess.run(
            ["npx", "--yes", "solc@0.8.18", "--standard-json"],
            stdin=infile, text=True, capture_output=True,
            timeout=180, check=False,
        )
    output = proc.stdout
    pos = output.find("{")
    if proc.returncode != 0 or pos < 0 or len(output) > 20_000_000:
        raise ValueError("AST compiler exited without bounded JSON")
    parsed = json.loads(output[pos:])
    if any(
        isinstance(item, dict) and item.get("severity") == "error"
        for item in parsed.get("errors", [])
    ):
        raise ValueError("AST compiler reported Solidity errors")
    src = parsed.get("sources")
    info = src.get("contracts/lendingpool/LendingPool.sol") if isinstance(src, dict) else None
    ast = info.get("ast") if isinstance(info, dict) else None
    if not isinstance(ast, dict):
        raise ValueError("compiler did not produce LendingPool AST")
    return ast


def fixture(snapshot: Any, rpc_evidence: Any, compiled_ast: Any = None) -> dict[str, str]:
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

    # Solidity immutableReferences keys are AST VariableDeclaration IDs. Find
    # the exact registry variable, rather than assuming a single immutable
    # across this contract and inherited modules.
    compiler_output = snapshot.get("stdJsonOutput")
    sources = compiler_output.get("sources") if isinstance(compiler_output, dict) else None
    source_info = sources.get("contracts/lendingpool/LendingPool.sol") if isinstance(sources, dict) else None
    ast = compiled_ast if compiled_ast is not None else (
        source_info.get("ast") if isinstance(source_info, dict) else None
    )
    matches = []
    def traverse(node):
        if isinstance(node, list):
            for child in node:
                traverse(child)
        elif isinstance(node, dict):
            if (
                node.get("nodeType") == "VariableDeclaration"
                and node.get("name") == "addressRegistry"
                and node.get("mutability") == "immutable"
                and node.get("stateVariable") is True
            ):
                matches.append(str(node.get("id")))
            for child in node.values():
                if isinstance(child, (dict, list)):
                    traverse(child)
    if isinstance(ast, dict):
        traverse(ast)
    if len(matches) != 1 or matches[0] not in ids or not isinstance(values, dict):
        raise ValueError(
            "cannot map registry immutable to unique compiler AST id: "
            f"found_ast_ids={matches[:8]}, runtime_ids={sorted(map(str, ids))[:12]}"
        )
    identity = matches[0]
    raw = hex_bytes(values.get(identity))
    if len(raw) != 32 or raw[:12] != bytes(12) or raw[12:] == bytes(20):
        raise ValueError("immutable is not a canonical nonzero Solidity address")
    # All instances of this immutable are already reference-map checked by
    # examine(). Validate the number of referenced spans as a final guard.
    refs = rt.get("immutableReferences", {}).get(identity)
    selected = [item for item in immutables if item.get("id") == identity]
    if not isinstance(refs, list) or len(refs) != len(selected):
        raise ValueError("registry immutable reference count is inconsistent")
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
        ast = compile_verified_ast(snap)
        data = fixture(snap, rpc, compiled_ast=ast)
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
