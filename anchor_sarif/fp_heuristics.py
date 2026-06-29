"""Rule-based signal filtering heuristics for the ANCHOR SARIF pipeline.

Pure functions only — no LLM, no separate validator object.
ANCHOR remains the sole reasoning layer (cluster summaries via injected callback).
"""

from __future__ import annotations

import re
from typing import Any

from .parser import Finding

_TEST_PATH_RE = re.compile(
    r"(^|/)(test|tests|mock|mocks|fixture|fixtures|forge-std|lib/|node_modules/|\.t\.sol)",
    re.IGNORECASE,
)
_REENTRANCY_GUARD_RE = re.compile(
    r"\b(nonReentrant|ReentrancyGuard|_status\s*==|_locked|mutex|reentrancy.?guard)\b",
    re.IGNORECASE,
)
_SOLC_08_RE = re.compile(r"pragma\s+solidity\s+(\^?0\.([89]|\d{2,}))", re.IGNORECASE)
_SAFE_MATH_RE = re.compile(
    r"\b(SafeMath|checked\s*\{|overflow|underflow|0\.8)\b",
    re.IGNORECASE,
)
_OZ_PATTERN_RE = re.compile(
    r"\b(OpenZeppelin|Ownable|AccessControl|Pausable|SafeERC20|ReentrancyGuard)\b",
    re.IGNORECASE,
)

NOISY_RULES: dict[str, set[str]] = {
    "slither": {
        "naming-convention",
        "solc-version",
        "pragma",
        "too-many-digits",
        "dead-code",
        "unused-return",
        "low-level-calls",
        "reentrancy-benign",
        "calls-loop",
        "timestamp",
        "block-timestamp",
        "assembly",
        "costly-loop",
        "similar-names",
        "external-function",
    },
    "mythril": {
        "Dependence on predictable environment variable",
        "Exception State",
        "State access after external call",
    },
    "aderyn": {
        "unused-import",
        "screaming-snake-case-immutable",
        "deprecated-oz-ownable",
    },
    "semgrep": {"generic.secrets", "generic.test"},
    "codeql": set(),
}

PROOF_GATE_TOOLS = {"halmos"}


def _match_noisy_rule(tool: str, rule_id: str, message: str) -> str | None:
    for noisy in NOISY_RULES.get(tool, set()):
        needle = noisy.lower()
        if needle in rule_id.lower() or needle in message.lower():
            return f"Noisy rule from {tool}: {noisy}"
    return None


def assess_signal_noise(finding: Finding, *, source_context: str | None = None) -> dict[str, Any]:
    """Score whether a finding is likely scanner noise (rule-based only)."""
    reasons: list[str] = []
    score = 0.0

    tool = (finding.tool or "unknown").lower()
    rule_id = (finding.rule_id or "").lower()
    message = finding.message or ""
    file_path = finding.file_path or ""
    blob = f"{rule_id} {message}".lower()

    if tool in PROOF_GATE_TOOLS or finding.properties.get("is_invariant"):
        return {
            "is_likely_false_positive": False,
            "confidence": 0.95,
            "reasons": ["Proof-gate tool or invariant finding"],
            "suggested_action": "promote",
        }

    noisy = _match_noisy_rule(tool, rule_id, message)
    if noisy:
        reasons.append(noisy)
        score += 0.45

    if _TEST_PATH_RE.search(file_path.replace("\\", "/")):
        reasons.append("Finding in test, mock, or library path")
        score += 0.35

    context = source_context or finding.snippet or ""
    combined = f"{context}\n{message}"

    cross_function_reentrancy = "reentrancy" in blob and any(
        kw in blob for kw in ("cross-function", "cross function", "emergencywithdraw", "secondary function")
    )
    if "reentrancy" in blob and _REENTRANCY_GUARD_RE.search(combined):
        if cross_function_reentrancy:
            reasons.append("Cross-function reentrancy should not be dismissed by a local guard snippet")
        else:
            reasons.append("Protected by common reentrancy mitigation pattern")
            score += 0.4

    if cross_function_reentrancy:
        reasons.append("Cross-function reentrancy pattern")
        score = max(0.0, score - 0.2)

    if any(kw in blob for kw in ("overflow", "underflow", "arithmetic")):
        if _SOLC_08_RE.search(combined) or _SAFE_MATH_RE.search(combined):
            reasons.append("Solidity >=0.8 checked math or SafeMath pattern")
            score += 0.35

    if _OZ_PATTERN_RE.search(combined) and any(
        kw in blob for kw in ("access", "owner", "onlyowner", "unprotected")
    ):
        reasons.append("Common OpenZeppelin access-control library pattern")
        score += 0.25

    if finding.level.lower() in {"note", "info", "none", "informational"}:
        reasons.append(f"Low severity level: {finding.level}")
        score += 0.2

    norm = finding.normalized or finding.properties.get("normalized") or {}
    if norm.get("category") == "General" and tool in {"slither", "aderyn"}:
        reasons.append("Generic category from fast static analyzer")
        score += 0.15

    confidence = min(1.0, score)
    is_fp = confidence >= 0.5
    if is_fp and confidence >= 0.7:
        action = "discard"
    elif is_fp:
        action = "review"
    elif confidence <= 0.35:
        action = "promote"
    else:
        action = "review"

    return {
        "is_likely_false_positive": is_fp,
        "confidence": round(confidence, 4),
        "reasons": reasons or ["No strong false-positive indicators"],
        "suggested_action": action,
    }


def should_drop_signal(assessment: dict[str, Any], *, threshold: float = 0.7) -> bool:
    return (
        assessment.get("is_likely_false_positive")
        and assessment.get("confidence", 0) >= threshold
        and assessment.get("suggested_action") == "discard"
    )
