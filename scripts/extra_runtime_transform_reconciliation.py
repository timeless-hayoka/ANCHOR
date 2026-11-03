#!/usr/bin/env python3
"""Strict, read-only Sourcify runtime transformation reconciliation.

A transformation reconciles *declared* onchain byte differences; it does not
certify immutable values, contract behavior, program scope, or a vulnerability.
All byte offsets are interpreted as byte offsets, never hex-string indices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CHAIN_ID = "10"
ADDRESS = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
URL = f"https://sourcify.dev/server/v2/contract/{CHAIN_ID}/{ADDRESS}?fields=all"
MAX_BYTES = 6_000_000
HEX = re.compile(r"^0x(?:[0-9a-fA-F]{2})+$")
ALLOWED_REASONS = {"cborAuxdata", "immutable", "library", "callProtection"}


def hex_bytes(value: Any) -> bytes:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("missing, malformed or empty hex bytecode/value")
    return bytes.fromhex(value[2:])


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def examine(snapshot: Any, rpc_evidence: Any = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "state": "NOT_RECONCILED",
        "chain_id": CHAIN_ID,
        "address": ADDRESS,
        "full_deployment_equivalence": "NOT_PROVEN",
        "finding": "NONE",
    }
    if not isinstance(snapshot, dict):
        report["reason"] = "invalid Sourcify response"
        return report
    if str(snapshot.get("chainId")) != CHAIN_ID or str(snapshot.get("address", "")).lower() != ADDRESS:
        report["reason"] = "wrong chain or address"
        return report
    if snapshot.get("runtimeMatch") not in {"match", "exact_match"}:
        report["reason"] = "no verified Sourcify runtime match"
        return report
    runtime = snapshot.get("runtimeBytecode")
    if not isinstance(runtime, dict):
        report["reason"] = "no runtime bytecode record"
        return report
    try:
        deployed = hex_bytes(runtime.get("onchainBytecode"))
        compiled = hex_bytes(runtime.get("recompiledBytecode"))
    except ValueError as exc:
        report["reason"] = str(exc)
        return report
    # Existing independent RPC/provenance reports hash the normalized 0x hex
    # representation, not decoded bytes. Preserve that wire-format convention.
    onchain_wire_sha = hashlib.sha256(("0x" + deployed.hex()).encode("utf-8")).hexdigest()
    recompiled_wire_sha = hashlib.sha256(("0x" + compiled.hex()).encode("utf-8")).hexdigest()
    report["onchain_sha256"] = onchain_wire_sha
    report["recompiled_sha256"] = recompiled_wire_sha
    report["onchain_byte_count"] = len(deployed)
    report["recompiled_byte_count"] = len(compiled)

    if rpc_evidence is not None:
        if not isinstance(rpc_evidence, dict):
            report["reason"] = "RPC attestation malformed"
            return report
        if (
            rpc_evidence.get("state") != "RPC_MATCHES_PROVIDER_ONCHAIN"
            or str(rpc_evidence.get("chain_id")) != CHAIN_ID
            or str(rpc_evidence.get("address", "")).lower() != ADDRESS
            or str(rpc_evidence.get("rpc_onchain_sha256", "")).lower() != onchain_wire_sha
            or str(rpc_evidence.get("provider_onchain_sha256", "")).lower() != onchain_wire_sha
            or rpc_evidence.get("transaction_broadcast") is not False
        ):
            report["reason"] = "independent onchain bytecode attestation incomplete or contradictory"
            return report
        report["rpc_attestation"] = "RPC_MATCHES_PROVIDER_ONCHAIN"
    else:
        report["rpc_attestation"] = "NOT_PROVIDED"

    if len(deployed) != len(compiled):
        report["reason"] = "runtime bytecode lengths differ; replacement-only reconciliation insufficient"
        return report
    if deployed == compiled:
        report["state"] = "BYTE_IDENTICAL_PROVIDER_RUNTIME"
        report["transformation_count"] = 0
        report["reason"] = "provider runtime bytes are identical; independent match depends on supplied RPC attestation"
        return report

    transformations = runtime.get("transformations")
    values = runtime.get("transformationValues")
    if not isinstance(transformations, list) or not transformations or not isinstance(values, dict):
        report["reason"] = "runtime differs but transformation evidence is absent"
        return report
    if len(transformations) > 256:
        report["reason"] = "unreasonable transformation count"
        return report

    masked = bytearray(len(deployed))
    patches: list[dict[str, Any]] = []
    for index, item in enumerate(transformations):
        if not isinstance(item, dict):
            report["reason"] = f"transformation {index} invalid"
            return report
        kind = item.get("type")
        reason = item.get("reason")
        offset = item.get("offset")
        identity = item.get("id")
        if kind != "replace" or reason not in ALLOWED_REASONS or type(offset) is not int or offset < 0:
            report["reason"] = f"unsupported transformation {index}"
            return report
        if reason in {"cborAuxdata", "immutable", "library"}:
            if not isinstance(identity, str) or not identity:
                report["reason"] = f"transformation {index} missing id"
                return report
        if reason == "cborAuxdata":
            group = values.get("cborAuxdata")
            encoded = group.get(identity) if isinstance(group, dict) else None
        elif reason == "immutable":
            group = values.get("immutables")
            encoded = group.get(identity) if isinstance(group, dict) else None
        elif reason == "library":
            group = values.get("libraries")
            encoded = group.get(identity) if isinstance(group, dict) else None
        else:
            encoded = values.get("callProtection")
        try:
            replacement = hex_bytes(encoded)
        except ValueError:
            report["reason"] = f"missing/invalid transformation value at {index}"
            return report
        if (reason in {"library", "callProtection"} and len(replacement) != 20):
            report["reason"] = f"transformation {index} invalid 20-byte address"
            return report
        if reason == "cborAuxdata":
            if len(replacement) < 2:
                report["reason"] = f"transformation {index} invalid metadata"
                return report
            # CBOR metadata length is encoded in the final two bytes by solc.
            declared = int.from_bytes(replacement[-2:], "big") + 2
            if declared != len(replacement):
                report["reason"] = f"transformation {index} has invalid CBOR length trailer"
                return report
        end = offset + len(replacement)
        if end > len(deployed) or any(masked[offset:end]):
            report["reason"] = f"transformation {index} overlaps or exceeds runtime"
            return report
        if deployed[offset:end] != replacement:
            report["reason"] = f"transformation {index} value does not equal onchain bytes"
            return report
        masked[offset:end] = b"\x01" * len(replacement)
        patches.append({"reason": reason, "offset": offset, "length": len(replacement)})

    unexplained = [
        i for i, (a, b) in enumerate(zip(deployed, compiled))
        if a != b and masked[i] == 0
    ]
    report["transformation_count"] = len(patches)
    report["transformations"] = patches
    report["changed_byte_count"] = sum(a != b for a, b in zip(deployed, compiled))
    report["unexplained_byte_count"] = len(unexplained)
    report["first_unexplained_offsets"] = unexplained[:20]
    if unexplained:
        report["reason"] = "runtime contains byte differences outside declared transformations"
        return report
    report["state"] = "DECLARED_TRANSFORMS_RECONCILED"
    report["reason"] = (
        "all byte differences are confined to validated Sourcify replacement "
        "locations; constructor-set immutables and library bindings require "
        "separate behavioral analysis, and this is not a vulnerability claim"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--rpc-evidence", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            raw = args.snapshot.read_bytes()
        else:
            request = urllib.request.Request(
                URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-transform-reconciliation"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Sourcify response too large")
        rpc = json.loads(args.rpc_evidence.read_text(encoding="utf-8")) if args.rpc_evidence else None
        report = examine(json.loads(raw.decode("utf-8")), rpc)
    except (OSError, ValueError, UnicodeError, urllib.error.URLError) as exc:
        report = {
            "state": "NOT_RECONCILED",
            "reason": f"comparison evidence unavailable: {type(exc).__name__}: {str(exc)[:160]}",
            "full_deployment_equivalence": "NOT_PROVEN",
            "finding": "NONE",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["state"] in {"DECLARED_TRANSFORMS_RECONCILED", "BYTE_IDENTICAL_PROVIDER_RUNTIME"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
