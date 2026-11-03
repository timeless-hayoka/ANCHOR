#!/usr/bin/env python3
"""Read-only OP Mainnet bytecode attestation against Sourcify metadata.

Uses eth_chainId, eth_blockNumber, and eth_getCode only; never broadcasts,
signs, or calls the contract. Matching Sourcify's onchain bytes does not
imply matching its recompiled bytecode when runtimeMatch is non-exact.
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
RPC_URL = "https://mainnet.optimism.io"
HEX_BYTES = re.compile(r"^0x[0-9a-fA-F]+$")


def rpc_request(method: str, params: list[Any]) -> Any:
    if method not in {"eth_chainId", "eth_blockNumber", "eth_getCode"}:
        raise ValueError("unapproved RPC method")
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(
        RPC_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ANCHOR-readonly-bytecode-audit"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("oversized RPC response")
    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, dict) or decoded.get("id") != 1 or decoded.get("jsonrpc") != "2.0":
        raise ValueError("malformed RPC response")
    if decoded.get("error") is not None or "result" not in decoded:
        raise ValueError("RPC error or missing result")
    return decoded["result"]


def attestation(provider: Any, *, rpc=rpc_request) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state": "NOT_ATTESTED",
        "chain_id": CHAIN_ID,
        "address": ADDRESS,
        "rpc_endpoint": RPC_URL,
        "rpc_methods": ["eth_chainId", "eth_blockNumber", "eth_getCode"],
        "full_deployment_equivalence": "NOT_PROVEN",
        "transaction_broadcast": False,
    }
    if not isinstance(provider, dict):
        result["reason"] = "missing provider provenance record"
        return result
    if (
        provider.get("state") != "PROVIDER_METADATA_RECORDED"
        or str(provider.get("chain_id")) != CHAIN_ID
        or str(provider.get("address", "")).lower() != ADDRESS
    ):
        result["reason"] = "provider provenance does not match this deployed target"
        return result
    expected = (provider.get("provider_runtime_bytecode") or {}).get("onchain_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        result["reason"] = "provider onchain bytecode digest unavailable"
        return result
    if rpc("eth_chainId", []) != "0xa":
        result["reason"] = "RPC returned wrong chain ID"
        return result
    block = rpc("eth_blockNumber", [])
    if not isinstance(block, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", block):
        result["reason"] = "RPC block number invalid"
        return result
    code = rpc("eth_getCode", [ADDRESS, block])
    if not isinstance(code, str) or not HEX_BYTES.fullmatch(code) or len(code) % 2 != 0 or code == "0x":
        result["reason"] = "contract code missing or malformed"
        return result
    normalized = code.lower()
    observed = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    result["queried_block"] = block
    result["rpc_onchain_sha256"] = observed
    result["provider_onchain_sha256"] = expected.lower()
    if observed != expected.lower():
        result["state"] = "RPC_PROVIDER_BYTECODE_MISMATCH"
        result["reason"] = "independent read-only RPC code differs from provider's onchain record"
    else:
        result["state"] = "RPC_MATCHES_PROVIDER_ONCHAIN"
        result["reason"] = (
            "read-only RPC deployed bytecode matched Sourcify's onchain digest; "
            "source recompiled-bytecode equivalence remains unproven"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        provider = json.loads(args.provider.read_text(encoding="utf-8"))
        result = attestation(provider)
    except (OSError, ValueError, UnicodeError, urllib.error.URLError) as exc:
        result = {
            "state": "NOT_ATTESTED",
            "reason": f"independent read-only RPC evidence unavailable: {type(exc).__name__}",
            "chain_id": CHAIN_ID,
            "address": ADDRESS,
            "full_deployment_equivalence": "NOT_PROVEN",
            "transaction_broadcast": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "RPC_MATCHES_PROVIDER_ONCHAIN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
