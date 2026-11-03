#!/usr/bin/env python3
"""Recompile Sourcify's verified Standard JSON input without RPC or broadcasts.

This validates reproducibility of a provider-described build, NOT deployed
bytecode equivalence. The compiler output is treated as untrusted data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

CHAIN_ID = "10"
ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
URL = f"https://sourcify.dev/server/v2/contract/{CHAIN_ID}/{ADDRESS}?fields=all"
SOURCE_PATH = "contracts/lendingpool/LendingPool.sol"
CONTRACT = "LendingPool"
MAX_BYTES = 6_000_000
SUPPORTED_COMPILER = "0.8.18"


def sha(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def prepare_input(snapshot: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(snapshot, dict):
        raise ValueError("missing Sourcify metadata")
    if str(snapshot.get("chainId")) != CHAIN_ID or str(snapshot.get("address", "")).lower() != ADDRESS:
        raise ValueError("wrong deployment")
    if snapshot.get("runtimeMatch") not in {"match", "exact_match"}:
        raise ValueError("unverified runtime")
    compilation = snapshot.get("compilation")
    if not isinstance(compilation, dict) or compilation.get("language") != "Solidity":
        raise ValueError("missing Solidity compilation settings")
    version = str(compilation.get("compilerVersion", ""))
    if not re.match(r"^v?0\.8\.18(?:\+|$)", version):
        raise ValueError("unapproved compiler version; must match deployed 0.8.18")
    std = snapshot.get("stdJsonInput")
    if not isinstance(std, dict) or std.get("language") != "Solidity":
        raise ValueError("missing Standard JSON compiler input")
    sources = std.get("sources")
    if not isinstance(sources, dict) or SOURCE_PATH not in sources or len(sources) > 200:
        raise ValueError("missing or unreasonable sources")
    for path, entry in sources.items():
        if (
            not isinstance(path, str) or not isinstance(entry, dict)
            or not isinstance(entry.get("content"), str)
        ):
            raise ValueError("source input missing embedded content")
    if not isinstance(std.get("settings"), dict):
        raise ValueError("missing compiler settings")
    copied = deepcopy(std)
    copied["settings"]["outputSelection"] = {
        "*": {"*": []},
        SOURCE_PATH: {CONTRACT: ["evm.deployedBytecode.object"]},
    }
    expected = (snapshot.get("runtimeBytecode") or {}).get("recompiledBytecode")
    if not isinstance(expected, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", expected):
        raise ValueError("missing Sourcify recompiled runtime bytecode")
    context = {
        "compiler_version": version,
        "source_count": len(sources),
        "source_sha256": sha(sources[SOURCE_PATH]["content"]),
        "provider_recompiled_sha256": sha(expected.lower()),
        "provider_runtime_match": snapshot["runtimeMatch"],
        "expected_recompiled_hex": expected.lower(),
    }
    return copied, context


def compare_compilation(compiled: Any, context: dict[str, Any]) -> dict[str, Any]:
    report = {
        "state": "COMPILE_NOT_PROVEN",
        "compiler_version": context["compiler_version"],
        "source_count": context["source_count"],
        "source_sha256": context["source_sha256"],
        "provider_runtime_match": context["provider_runtime_match"],
        "independent_rpc_check": "NOT_PERFORMED",
        "full_deployment_equivalence": "NOT_PROVEN",
    }
    if not isinstance(compiled, dict):
        report["reason"] = "compiler response not an object"
        return report
    errors = [
        str(item.get("formattedMessage") or item.get("message") or "")[:450]
        for item in compiled.get("errors", [])
        if isinstance(item, dict) and item.get("severity") == "error"
    ] if isinstance(compiled.get("errors", []), list) else ["malformed compiler diagnostics"]
    if errors:
        report["reason"] = "compiler errors"
        report["compiler_errors_first_3"] = errors[:3]
        return report
    contracts = compiled.get("contracts")
    result = (
        contracts.get(SOURCE_PATH, {}).get(CONTRACT, {})
        if isinstance(contracts, dict) and isinstance(contracts.get(SOURCE_PATH), dict)
        else {}
    )
    obj = ((result.get("evm") or {}).get("deployedBytecode") or {}).get("object")
    if not isinstance(obj, str) or not re.fullmatch(r"[0-9a-fA-F]+", obj):
        report["reason"] = "compiler runtime output missing or unlinked"
        return report
    actual = "0x" + obj.lower()
    expected = context["expected_recompiled_hex"]
    report["state"] = "PROVIDER_BUILD_COMPILED"
    report["compiler_recompiled_sha256"] = sha(actual)
    report["provider_recompiled_sha256"] = sha(expected)
    report["compiler_equals_provider_recompiled"] = actual == expected
    report["reason"] = (
        "locally compiled provider Standard JSON input; this does not attest "
        "deployed runtime or approved bounty scope"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, help="Optional offline Sourcify JSON")
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            raw = args.snapshot.read_bytes()
        else:
            request = urllib.request.Request(
                URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-build-repro"}
            )
            with urllib.request.urlopen(request, timeout=20) as stream:
                raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("provider response too large")
        std, context = prepare_input(json.loads(raw.decode("utf-8")))
        command = ["npx", "--yes", "solc@0.8.18", "--standard-json"]
        completed = subprocess.run(
            command, input=json.dumps(std), text=True, capture_output=True,
            timeout=180, check=False,
        )
        # solcjs may print an SMT advisory before its JSON output.
        output = completed.stdout
        start = output.find("{")
        if completed.returncode != 0 or start < 0 or len(output) > 20_000_000:
            detail = completed.stderr[-450:].replace("\\n", " ")
            raise ValueError(
                f"compiler failed (returncode={completed.returncode}, "
                f"stdout_bytes={len(output)}, stderr_tail={detail})"
            )
        report = compare_compilation(json.loads(output[start:]), context)
    except (ValueError, TypeError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        report = {
            "state": "COMPILE_NOT_PROVEN",
            "reason": f"build evidence unavailable: {type(exc).__name__}: {str(exc)[:220]}",
            "independent_rpc_check": "NOT_PERFORMED",
            "full_deployment_equivalence": "NOT_PROVEN",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["state"] == "PROVIDER_BUILD_COMPILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
