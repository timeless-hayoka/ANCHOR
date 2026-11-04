#!/usr/bin/env python3
"""Bounded, read-only historical Extra Finance vault deployment provenance.

Queries only public JSON-RPC read methods, fails closed on mismatches,
and records hashes/lengths instead of reproducing raw bytecode or traces.
No eth_sendRawTransaction, signing, state overrides or simulated outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

TX = "0xbdd878d0e7cdf19d7a25013839ac5a9ff677b923a6a42c4c41eba2583b3d4459"
FACTORY = "0x155620a2e6a9392c754b73296d9655061525729b"
SENDER = "0x9088b976e9542d0a27f4f9ddc7a716c7714806ea"
VAULT = "0x5101081495d209a80f5dbb1c5ecd76fe137a9ee9"
CREATE_BLOCK = 96_268_610
STUDY_BLOCK = 120_000_000
EXPECTED_CODEHASH = "0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480"
MAX_TRACE_DEPTH = 14
MAX_TRACE_NODES = 120


class ProvenanceError(Exception):
    pass


def rpc(url: str, method: str, params: list, request_id: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": request_id,
                         "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "ANCHOR-readonly-provenance/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("id") != request_id:
        raise ProvenanceError("malformed RPC response or request id")
    return payload


def need_result(response: dict, name: str):
    if response.get("error") is not None:
        raise ProvenanceError(f"{name}: RPC returned error: {response['error'].get('message', 'unknown')}")
    result = response.get("result")
    if result is None:
        raise ProvenanceError(f"{name}: missing result")
    return result


def normalized_address(value: str | None) -> str:
    if not isinstance(value, str) or len(value) != 42:
        raise ProvenanceError("missing or malformed address")
    return value.lower()


def bytecode_fingerprint(code: str) -> dict:
    if not isinstance(code, str) or not code.startswith("0x") or len(code) % 2:
        raise ProvenanceError("malformed returned bytecode")
    try:
        raw = bytes.fromhex(code[2:])
    except ValueError as exc:
        raise ProvenanceError("non-hex bytecode") from exc
    if not raw:
        raise ProvenanceError("historical contract bytecode not available")
    result = {"byte_length": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if shutil.which("cast"):
        hashed = subprocess.run(["cast", "keccak", code], capture_output=True, text=True,
                                timeout=15, check=True).stdout.strip()
        if not hashed.startswith("0x") or len(hashed) != 66:
            raise ProvenanceError("bad cast-keccak response")
        result["keccak256_runtime"] = hashed.lower()
    else:
        result["keccak256_runtime"] = None
    return result


def trace_summary(root: dict) -> dict:
    if not isinstance(root, dict):
        raise ProvenanceError("trace returned non-object")
    nodes: list[dict] = []
    queue = [(root, 0)]
    while queue and len(nodes) < MAX_TRACE_NODES:
        current, depth = queue.pop(0)
        if not isinstance(current, dict) or depth > MAX_TRACE_DEPTH:
            continue
        kind = str(current.get("type", "UNKNOWN")).upper()
        fragment = {"depth": depth, "type": kind,
                    "from": current.get("from"), "to": current.get("to"),
                    "error": current.get("error")}
        raw_input = current.get("input")
        if isinstance(raw_input, str) and raw_input.startswith("0x"):
            fragment["input_bytes"] = max(0, (len(raw_input) - 2) // 2)
            fragment["input_sha256"] = hashlib.sha256(bytes.fromhex(raw_input[2:])).hexdigest()
            fragment["selector"] = raw_input[:10] if len(raw_input) >= 10 else None
        nodes.append(fragment)
        for child in (current.get("calls") or []):
            queue.append((child, depth + 1))
    return {"nodes": nodes, "truncated": bool(queue), "max_nodes": MAX_TRACE_NODES,
            "note": "Call-tracer summary only; bytecode and calldata deliberately omitted"}


def collect(url: str) -> dict:
    call_id = 0

    def read(method: str, params: list):
        nonlocal call_id
        call_id += 1
        return need_result(rpc(url, method, params, call_id), method)

    if int(read("eth_chainId", []), 16) != 10:
        raise ProvenanceError("RPC endpoint is not Optimism chain 10")

    tx = read("eth_getTransactionByHash", [TX])
    if int(tx["blockNumber"], 16) != CREATE_BLOCK:
        raise ProvenanceError("transaction creation block mismatch")
    if normalized_address(tx.get("from")) != SENDER:
        raise ProvenanceError("creation sender mismatch")
    if normalized_address(tx.get("to")) != FACTORY:
        raise ProvenanceError("creation factory mismatch")
    data = tx.get("input", "")
    if not isinstance(data, str) or not data.startswith("0xf18efb45") or len(data) != 906:
        raise ProvenanceError("creation input changed or missing")
    receipt = read("eth_getTransactionReceipt", [TX])
    if int(receipt["blockNumber"], 16) != CREATE_BLOCK or int(receipt["status"], 16) != 1:
        raise ProvenanceError("creation transaction receipt failed or wrong block")
    if normalized_address(receipt["to"]) != FACTORY:
        raise ProvenanceError("receipt factory mismatch")

    creation_tag = hex(CREATE_BLOCK)
    study_tag = hex(STUDY_BLOCK)
    factory_then = bytecode_fingerprint(read("eth_getCode", [FACTORY, creation_tag]))
    factory_now = bytecode_fingerprint(read("eth_getCode", [FACTORY, study_tag]))
    vault_then = bytecode_fingerprint(read("eth_getCode", [VAULT, creation_tag]))
    vault_now = bytecode_fingerprint(read("eth_getCode", [VAULT, study_tag]))
    if vault_now.get("keccak256_runtime") and vault_now["keccak256_runtime"] != EXPECTED_CODEHASH:
        raise ProvenanceError("historic study vault runtime codehash mismatch")
    evidence = {
        "schema_version": "1.0", "chain_id": 10, "creation_block": CREATE_BLOCK,
        "study_block": STUDY_BLOCK, "transaction_hash": TX, "sender": SENDER,
        "factory": FACTORY, "vault": VAULT,
        "transaction_selector": data[:10],
        "transaction_input_bytes": (len(data) - 2) // 2,
        "transaction_input_sha256": hashlib.sha256(bytes.fromhex(data[2:])).hexdigest(),
        "factory_creation_code": factory_then,
        "factory_study_code": factory_now,
        "factory_runtime_equal_across_blocks": factory_then["sha256"] == factory_now["sha256"],
        "vault_creation_code": vault_then,
        "vault_study_code": vault_now,
        "vault_runtime_equal_across_blocks": vault_then["sha256"] == vault_now["sha256"],
        "trace": {"status": "NOT_PROBED"},
        "source_equivalence": "UNKNOWN",
        "vault_creation_version": "UNKNOWN",
        "liquidation_eligibility": "UNKNOWN",
        "liquidation_replay": "NOT_ATTEMPTED",
        "production_mutation": False,
    }
    # Trace RPC is optional. A missing trace is a failure to obtain
    # provenance, not evidence that no delegatecall or CREATE2 occurred.
    try:
        response = rpc(url, "debug_traceTransaction",
                       [TX, {"tracer": "callTracer", "timeout": "12s"}], call_id + 1)
        if response.get("error") is not None:
            evidence["trace"] = {"status": "UNAVAILABLE",
                                 "reason": str(response["error"].get("message", "RPC error"))[:200]}
        elif isinstance(response.get("result"), dict):
            evidence["trace"] = {"status": "AVAILABLE",
                                 "summary": trace_summary(response["result"])}
        else:
            evidence["trace"] = {"status": "UNAVAILABLE", "reason": "unexpected payload"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        evidence["trace"] = {"status": "UNAVAILABLE", "reason": type(exc).__name__}
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc-url", default=os.environ.get("OP_READONLY_RPC", "https://mainnet.optimism.io"))
    parser.add_argument("--out", default="evidence/extra_vault3_rpc_creation_readout.json")
    args = parser.parse_args()
    if not args.rpc_url.startswith("https://"):
        print("Requires HTTPS public RPC endpoint", file=sys.stderr)
        return 2
    try:
        evidence = collect(args.rpc_url)
    except (ProvenanceError, urllib.error.URLError, TimeoutError, OSError,
            ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print("INCONCLUSIVE: " + str(exc)[:400], file=sys.stderr)
        return 1
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Creation factory code equivalent across blocks:", evidence["factory_runtime_equal_across_blocks"])
    print("Vault runtime equivalent across blocks:", evidence["vault_runtime_equal_across_blocks"])
    print("Creation trace availability:", evidence["trace"]["status"])
    print("Liquidation eligibility:", evidence["liquidation_eligibility"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
