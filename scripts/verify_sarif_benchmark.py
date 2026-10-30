#!/usr/bin/env python3
"""Fail closed on malformed or regressed SARIF known-findings benchmark evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def verify(payload: dict) -> list[str]:
    errors = []
    results = payload.get("results")
    summary = payload.get("results_summary")
    if not isinstance(results, list) or not results:
        return ["benchmark must contain at least one evaluated case"]
    if not isinstance(summary, dict):
        return ["missing results_summary"]
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            errors.append(f"case {index}: invalid record")
            continue
        expected = result.get("expected_visible")
        actual = result.get("actual_visible")
        if not isinstance(expected, bool) or not isinstance(actual, bool):
            errors.append(f"case {index}: visibility must be boolean")
            continue
        classification = ("TP" if actual else "FN") if expected else ("FP" if actual else "TN")
        if result.get("classification") != classification:
            errors.append(f"case {index}: inconsistent classification")
        if result.get("status") != ("PASSED" if classification in ("TP", "TN") else "FAILED"):
            errors.append(f"case {index}: inconsistent status")
        counts[classification] += 1
    expected_fields = {"cases": len(results), "true_positives": counts["TP"],
                       "false_positives": counts["FP"], "false_negatives": counts["FN"],
                       "true_negatives": counts["TN"], "passed": counts["TP"] + counts["TN"],
                       "failed": counts["FP"] + counts["FN"]}
    for key, expected in expected_fields.items():
        value = summary.get(key)
        if type(value) is not int or value != expected:
            errors.append(f"summary {key}: expected {expected}, got {value!r}")
    if counts["FP"] or counts["FN"]:
        errors.append(f"known-findings regression: FP={counts['FP']}, FN={counts['FN']}")
    if counts["TP"] == 0:
        errors.append("no positive controls: benchmark cannot demonstrate detection")
    if counts["TN"] == 0:
        errors.append("no negative controls: benchmark cannot demonstrate rejection")
    return errors


def main() -> int:
    root = Path("benchmarks/sarif-known-findings/runs")
    reports = sorted(root.glob("*/benchmark.json"), key=lambda p: p.stat().st_mtime)
    if not reports:
        print("FAIL: no generated benchmark.json found", file=sys.stderr)
        return 1
    try:
        payload = json.loads(reports[-1].read_text(encoding="utf-8"))
        errors = verify(payload)
    except (ValueError, OSError, TypeError) as exc:
        print(f"FAIL: unreadable benchmark: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"PASS: {len(payload['results'])} labeled cases; no FP/FN; positive and negative controls verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
