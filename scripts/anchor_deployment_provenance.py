#!/usr/bin/env python3
"""Read-only Sourcify deployment provenance, without optimistic parity claims.

Captures bounded compiler/build and runtime bytecode metadata for reproducible
source-version triage. Provider responses are evidence, NOT independent RPC
attestation, automatic authorization, or an exploitable finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CHAIN_ID = "10"
ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
URL = f"https://sourcify.dev/server/v2/contract/{CHAIN_ID}/{ADDRESS}?fields=all"
MAX_BYTES = 6_000_000


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def analyze(snapshot: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "chain_id": CHAIN_ID,
        "address": ADDRESS,
        "state": "NOT_VERIFIED",
        "provider": "Sourcify API v2",
        "independent_rpc_bytecode_check": "NOT_PERFORMED",
        "full_deployment_equivalence": "NOT_PROVEN",
    }
    if not isinstance(snapshot, dict):
        result["reason"] = "invalid source metadata object"
        return result
    if str(snapshot.get("chainId")) != CHAIN_ID or str(snapshot.get("address", "")).lower() != ADDRESS:
        result["reason"] = "chain or deployment identity differs"
        return result
    match = snapshot.get("runtimeMatch")
    if match not in ("match", "exact_match"):
        result["reason"] = "Sourcify runtime verification unavailable"
        return result
    result["state"] = "PROVIDER_METADATA_RECORDED"
    result["runtime_match"] = match
    compilation = snapshot.get("compilation")
    if isinstance(compilation, dict):
        result["compiler"] = {
            "language": compilation.get("language"),
            "name": compilation.get("name"),
            "compiler_version": compilation.get("compilerVersion"),
            "fully_qualified_name": compilation.get("fullyQualifiedName"),
        }
        settings = compilation.get("compilerSettings")
        if isinstance(settings, dict):
            result["compiler_settings_sha256"] = digest(
                json.dumps(settings, separators=(",", ":"), sort_keys=True)
            )
            optimizer = settings.get("optimizer")
            if isinstance(optimizer, dict):
                result["optimizer"] = {
                    "enabled": optimizer.get("enabled"),
                    "runs": optimizer.get("runs"),
                }
        else:
            result["compiler_settings_status"] = "MISSING"
    else:
        result["compiler_status"] = "MISSING"

    sources = snapshot.get("sources")
    if isinstance(sources, dict):
        result["verified_source_count"] = len(sources)
        matches = [
            (path, entry.get("content") if isinstance(entry, dict) else entry)
            for path, entry in sources.items()
            if isinstance(path, str) and path.rsplit("/", 1)[-1] == "LendingPool.sol"
        ]
        if len(matches) == 1 and isinstance(matches[0][1], str):
            result["verified_lendingpool_path"] = matches[0][0]
            result["verified_lendingpool_sha256"] = digest(matches[0][1])

    runtime = snapshot.get("runtimeBytecode")
    if isinstance(runtime, dict):
        onchain = runtime.get("onchainBytecode")
        recompiled = runtime.get("recompiledBytecode")
        if all(isinstance(value, str) and value.startswith("0x") and len(value) >= 4
               and len(value) % 2 == 0 and
               all(letter in "0123456789abcdefABCDEF" for letter in value[2:])
               for value in (onchain, recompiled)):
            onchain = onchain.lower()
            recompiled = recompiled.lower()
            result["provider_runtime_bytecode"] = {
                "onchain_sha256": digest(onchain),
                "recompiled_sha256": digest(recompiled),
                "byte_identical_in_provider_response": onchain == recompiled,
            }
        else:
            result["provider_runtime_bytecode"] = {"state": "MISSING_OR_MALFORMED"}
    else:
        result["provider_runtime_bytecode"] = {"state": "MISSING_OR_MALFORMED"}
    proxy = snapshot.get("proxyResolution")
    if isinstance(proxy, dict):
        result["proxy"] = {
            "is_proxy": proxy.get("isProxy"),
            "type": proxy.get("proxyType"),
            "implementation_addresses": [
                value["address"]
                for value in (proxy.get("implementations") or [])
                if isinstance(value, dict) and isinstance(value.get("address"), str)
            ][:12],
        }
    result["reason"] = (
        "Sourcify provider metadata captured; independent RPC code check "
        "and exact deployed-source/build equivalence are not established"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Offline Sourcify v2 fields=all JSON")
    parser.add_argument("--output", type=Path, help="Write public provenance report JSON")
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            raw = args.snapshot.read_bytes()
        else:
            request = urllib.request.Request(
                URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-readonly-provenance"}
            )
            with urllib.request.urlopen(request, timeout=15) as stream:
                raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Sourcify response too large")
        result = analyze(json.loads(raw.decode("utf-8")))
    except (OSError, ValueError, UnicodeError, urllib.error.URLError) as exc:
        result = {
            "state": "NOT_VERIFIED", "chain_id": CHAIN_ID, "address": ADDRESS,
            "reason": f"public metadata unavailable: {type(exc).__name__}",
            "full_deployment_equivalence": "NOT_PROVEN",
        }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["state"] == "PROVIDER_METADATA_RECORDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
