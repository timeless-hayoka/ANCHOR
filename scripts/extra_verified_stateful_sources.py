#!/usr/bin/env python3
"""Materialize Sourcify-verified Solidity sources for an isolated Foundry lab.

Only public, embedded source content is written, never external URL fetches,
live RPC writes, or a repository checkout substituted for verified source.
The target LendingPool SHA and standard-json compiler details are pinned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

from extra_verified_source_compile import (
    ADDRESS, CHAIN_ID, MAX_BYTES, SOURCE_PATH, URL, prepare_input,
)

VERIFIED_LENDINGPOOL_SHA256 = "9e1a6cf5930e2477aab0022536be39ab4bb7e1fbb6953b31cf90429f6205bf6f"
SAFE_FRAGMENT = re.compile(r"^[A-Za-z0-9_.@+-]+$")


def prepare_files(snapshot: Any) -> dict[str, str]:
    std, context = prepare_input(snapshot)
    if context["source_sha256"] != VERIFIED_LENDINGPOOL_SHA256:
        raise ValueError("verified LendingPool source hash changed")
    if str(snapshot.get("chainId")) != CHAIN_ID or str(snapshot.get("address", "")).lower() != ADDRESS:
        raise ValueError("deployment identity mismatch")
    source_files = {}
    for path, record in std["sources"].items():
        pure = PurePosixPath(path)
        if (
            pure.is_absolute()
            or len(pure.parts) == 0
            or any(piece in ("", ".", "..") or not SAFE_FRAGMENT.fullmatch(piece) for piece in pure.parts)
            or not path.startswith("contracts/")
            or not path.endswith(".sol")
        ):
            raise ValueError(f"unsafe source path: {path[:120]}")
        source_files[path] = record["content"]
    if not 20 <= len(source_files) <= 100 or SOURCE_PATH not in source_files:
        raise ValueError("incomplete verified compilation sources")
    return source_files


def write_sources(outdir: Path, files: dict[str, str]) -> dict[str, Any]:
    if outdir.exists():
        raise ValueError("source destination must not exist")
    outdir.mkdir(parents=True)
    for path, content in files.items():
        dest = outdir.joinpath(*PurePosixPath(path).parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    report = {
        "state": "VERIFIED_SOURCE_TREE_MATERIALIZED",
        "chain_id": CHAIN_ID,
        "deployed_address": ADDRESS,
        "compiler": "0.8.18",
        "file_count": len(files),
        "lendingpool_sha256": hashlib.sha256(files[SOURCE_PATH].encode("utf-8")).hexdigest(),
        "deployment_equivalence": "NOT_PROVEN_BY_SOURCE_TREE_ALONE",
        "live_transactions": False,
    }
    (outdir / "anchor_verified_source_manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="offline Sourcify fields=all snapshot")
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            data = args.snapshot.read_bytes()
        else:
            request = urllib.request.Request(
                URL, headers={"Accept": "application/json", "User-Agent": "ANCHOR-verified-source-stateful-lab"}
            )
            with urllib.request.urlopen(request, timeout=20) as stream:
                data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Sourcify response exceeds size limit")
        files = prepare_files(json.loads(data.decode("utf-8")))
        report = write_sources(args.outdir, files)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({"state": "NOT_MATERIALIZED", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
