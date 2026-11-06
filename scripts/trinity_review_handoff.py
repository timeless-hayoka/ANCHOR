#!/usr/bin/env python3
"""Run a local, fail-closed Trinity artifact handoff from an evidence JSON bundle.

This does NOT acquire chain data, execute a PoC, or authenticate input provenance.
Use only reviewed, locally stored evidence bundles.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trinity_proof_handoff import HandoffRejected, review_case

MAX_BYTES = 1_000_000


def run(bundle_path: Path, output_path: Path) -> dict:
    with bundle_path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HandoffRejected("bundle exceeds size limit")
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "finder", "foundry", "watcher", "council"
    }:
        raise HandoffRejected("bundle must contain exactly finder/foundry/watcher/council")
    record = review_case(payload["finder"], payload["foundry"],
                         payload["watcher"], payload["council"])
    output = {
        "status": "COUNCIL_ACCEPTED_PENDING_REPORT_REVIEW",
        "lead": record.to_dict(),
        "finding_confirmed_onchain": False,
    }
    # Exclusive create: never replace another researcher's evidence or follow
    # a pre-existing output symlink.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(output_path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(output, out, sort_keys=True, indent=2)
            out.write("\n")
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.bundle, args.output)
    except (HandoffRejected, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"Trinity handoff rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "lead_id": result["lead"]["lead_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
