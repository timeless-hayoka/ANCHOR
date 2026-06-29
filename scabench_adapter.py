from __future__ import annotations

from typing import Any


def adapt(entry: dict[str, Any] | None) -> dict[str, Any]:
    payload = entry or {}
    summary = payload.get("results_summary") or {}
    confidence = payload.get("confidence_ladder") or {}

    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    timed_out = int(summary.get("timed_out", 0) or 0)
    detector_signals = int(summary.get("detector_signals", 0) or 0)
    environment_sensitive = int(summary.get("environment_sensitive", 0) or 0)

    raw_score = 50 + passed * 4 - failed * 5 - timed_out * 3 + detector_signals * 2 - environment_sensitive * 4
    if confidence.get("methodology") == "high":
        raw_score += 6
    if confidence.get("reproduction") == "high":
        raw_score += 6
    if confidence.get("comparative_data") == "not_yet":
        raw_score -= 4

    score = max(0, min(100, raw_score))
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "E"

    return {
        "adapter": "scabench",
        "score": score,
        "grade": grade,
        "summary": f"ScaBench score {score}/100 for {passed} passed, {failed} failed, {timed_out} timed out checks.",
        "signals": {
            "detector_signals": detector_signals,
            "environment_sensitive": environment_sensitive,
        },
    }
