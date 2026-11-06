"""Read-only, two-provider authentication of historical Extra Finance registry data.

This verifies observed historical snapshots; it does not establish executed
delegatecall targets, source equivalence, or liquidation eligibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request

REGISTRY = "0x85603119c938750dfb5904f8a501b64f3f3a01d2"
FACTORY = "0x155620a2e6a9392c754b73296d9655061525729b"
VAULT = "0x5101081495d209a80f5dbb1c5ecd76fe137a9ee9"
GET_ADDRESS_SELECTOR = "0xb93f9b0a"  # getAddress(uint256)
BLOCKS = {"creation": 96268610, "study": 120000000}
KEYS = [101, 103, 107, (1 << 128) | 1001, (1 << 128) | 1003]
EXPECTED_FACTORY_SHA256 = "cd24d04eabb10e59f3960de0c0da49fffc68e5e4c6d5edf13b14d1bbecf60417"
EXPECTED_VAULT_SHA256 = "1668b88f8fe84437f9459e8ea6cb22444d029963a6a8368ce02b52fecb1842b4"


class AuthenticationError(ValueError):
    pass


def rpc(url, method, params, request_id):
    req = urllib.request.Request(
        url, data=json.dumps({"jsonrpc": "2.0", "id": request_id,
                              "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("id") != request_id or payload.get("error") is not None:
        raise AuthenticationError("RPC response error or id mismatch")
    if payload.get("result") is None:
        raise AuthenticationError("RPC result missing")
    return payload["result"]


def require_hex(value, size):
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 2 + size * 2:
        raise AuthenticationError("invalid hexadecimal response size")
    try:
        return bytes.fromhex(value[2:])
    except ValueError as exc:
        raise AuthenticationError("invalid hexadecimal response") from exc


def observe(url, block_number):
    counter = 0
    def read(method, params):
        nonlocal counter
        counter += 1
        return rpc(url, method, params, counter)
    if read("eth_chainId", []) != "0xa":
        raise AuthenticationError("incorrect chain id")
    block = read("eth_getBlockByNumber", [hex(block_number), False])
    if not isinstance(block, dict) or int(block.get("number", "-1"), 16) != block_number:
        raise AuthenticationError("incorrect historical block")
    block_hash = block.get("hash")
    require_hex(block_hash, 32)
    # Bind every historical state read to the canonical hash (EIP-1898).
    # Providers lacking support fail closed; never downgrade to block numbers.
    block_ref = {"blockHash": block_hash, "requireCanonical": True}
    code_hashes = {}
    for address, label, expected in (
        (FACTORY, "factory", EXPECTED_FACTORY_SHA256),
        (VAULT, "vault", EXPECTED_VAULT_SHA256),
        (REGISTRY, "registry", None),
    ):
        raw = read("eth_getCode", [address, block_ref])
        code = require_hex(raw, (len(raw) - 2) // 2)
        if not code:
            raise AuthenticationError("historical runtime missing")
        digest = hashlib.sha256(code).hexdigest()
        if expected is not None and digest != expected:
            raise AuthenticationError("historical runtime differs from pinned evidence")
        code_hashes[label] = digest
    entries = {}
    for key in KEYS:
        calldata = GET_ADDRESS_SELECTOR + f"{key:064x}"
        value = read("eth_call", [{"to": REGISTRY, "data": calldata}, block_ref])
        raw = require_hex(value, 32)
        if any(raw[:12]):
            raise AuthenticationError("registry returned non-address word")
        entries[str(key)] = None if not any(raw[12:]) else "0x" + raw[12:].hex()
    check = read("eth_getBlockByNumber", [hex(block_number), False])
    if not isinstance(check, dict) or check.get("hash", "").lower() != block_hash.lower():
        raise AuthenticationError("historical block hash changed during reads")
    return {"chain_id": 10, "block_number": block_number,
            "block_hash": block_hash.lower(), "registry_address": REGISTRY,
            "factory_address": FACTORY, "vault_address": VAULT,
            "runtime_sha256": code_hashes, "registry_entries": entries}


def authenticate(first_url, second_url, pinned):
    if not first_url.startswith("https://") or not second_url.startswith("https://") or first_url == second_url:
        raise AuthenticationError("two distinct HTTPS RPC endpoints required")
    if pinned.get("provenance", {}).get("chain_id") != 10:
        raise AuthenticationError("pinned chain mismatch")
    if pinned.get("registry", {}).get("address", "").lower() != REGISTRY:
        raise AuthenticationError("pinned registry mismatch")
    observations = {}
    for label, height in BLOCKS.items():
        a = observe(first_url, height)
        b = observe(second_url, height)
        if a != b:
            raise AuthenticationError("independent provider observations disagree")
        if a["registry_entries"] != pinned["registry"][label]:
            raise AuthenticationError("live historical registry differs from pinned snapshot")
        observations[label] = a
    return {"status": "AUTHENTICATED_TWO_PROVIDER", "observations": observations,
            "trace": "UNAVAILABLE", "source_equivalence": "UNKNOWN",
            "liquidation_eligibility": "UNKNOWN"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc-a", default=os.environ.get("OP_ARCHIVE_RPC_A"))
    parser.add_argument("--rpc-b", default=os.environ.get("OP_ARCHIVE_RPC_B"))
    parser.add_argument("--pinned", default="evidence/extra_finance_2023_vs_2024_factory_registry_drift.json")
    parser.add_argument("--out", default="evidence/extra_registry_two_provider_auth.json")
    args = parser.parse_args()
    if not args.rpc_a or not args.rpc_b:
        parser.error("two independent archive RPC URLs required")
    pinned = json.loads(Path(args.pinned).read_text(encoding="utf-8"))
    report = authenticate(args.rpc_a, args.rpc_b, pinned)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["status"])


if __name__ == "__main__":
    main()
