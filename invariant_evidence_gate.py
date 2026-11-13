"""Deterministic, offline invariant evidence evaluation.

Consumes observations produced by the existing authorized analysis pipeline.
Never executes target code, grants scope, or claims vulnerability reproduction.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

OPERATORS = frozenset({"eq", "lte", "gte"})
MAX_BYTES = 1_000_000


def _number(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("numeric observations must be integer or decimal strings")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid numeric observation") from exc
    if not result.is_finite():
        raise ValueError("nonfinite numeric observation")
    return result


def evaluate_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict) or set(manifest) != {"target_ref", "observations", "invariants"}:
        raise ValueError("manifest fields must be target_ref, observations, invariants")
    ref, observations, invariants = (manifest[key] for key in ("target_ref", "observations", "invariants"))
    if not isinstance(ref, str) or len(ref) != 40 or any(c not in "0123456789abcdefABCDEF" for c in ref):
        raise ValueError("target_ref must be a pinned 40-character git SHA")
    if not isinstance(observations, dict) or not isinstance(invariants, list) or len(invariants) > 1000:
        raise ValueError("invalid observations or invariant list")
    if not all(isinstance(k, str) and k and len(k) <= 128 for k in observations):
        raise ValueError("invalid observation key")
    values = {k: _number(v) for k, v in observations.items()}
    results = []
    seen = set()
    for check in invariants:
        if not isinstance(check, dict) or set(check) != {"id", "left", "op", "right"}:
            raise ValueError("invalid invariant structure")
        identifier, left, op, right = (check[k] for k in ("id", "left", "op", "right"))
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("duplicate or invalid invariant id")
        seen.add(identifier)
        if op not in OPERATORS or not isinstance(left, str) or not isinstance(right, str):
            raise ValueError("invalid invariant operation")
        if left not in values or right not in values:
            raise ValueError("unknown observation reference")
        a, b = values[left], values[right]
        passed = {"eq": a == b, "lte": a <= b, "gte": a >= b}[op]
        results.append({"id": identifier, "status": "PASS" if passed else "FAIL",
                        "left": left, "right": right, "op": op})
    return {"target_ref": ref.lower(), "status": "FAIL" if any(x["status"] == "FAIL" for x in results) else "PASS",
            "checks": results, "validation_state": "UNVERIFIED_OBSERVATIONS"}


def self_check() -> None:
    base = {"target_ref": "a" * 40, "observations": {"before": "100", "after": "100"},
            "invariants": [{"id": "conservation", "left": "before", "op": "eq", "right": "after"}]}
    assert evaluate_manifest(base)["status"] == "PASS"
    broken = {**base, "observations": {"before": "100", "after": "99"}}
    assert evaluate_manifest(broken)["status"] == "FAIL"
    try:
        evaluate_manifest({**base, "invariants": [{"id": "bad", "left": "missing", "op": "eq", "right": "after"}]})
    except ValueError:
        pass
    else:
        raise AssertionError("malformed reference was accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check()
    if args.self_check:
        print("self-check PASS")
        return 0
    if args.manifest is None:
        parser.error("--manifest is required unless --self-check is used")
    raw = args.manifest.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("manifest exceeds size limit")
    print(json.dumps(evaluate_manifest(json.loads(raw)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
