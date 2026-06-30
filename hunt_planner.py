"""Structured hunt planning for ANCHOR.

This module turns a target note plus repo context into a falsifiable hunt plan:

scope -> hypothesis -> evidence -> reproduction -> review
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from anchor_strategy import compute_strategy


HUNT_MODULE_LIBRARY = [
    {
        "name": "Authorization Boundary Review",
        "match": re.compile(r"auth|authorization|permission|permissioned|access control", re.I),
        "why": "The target description points at a gate, so start by proving whether the gate actually blocks unauthorized callers.",
        "signals": [
            "missing or bypassed permission check",
            "wrapper function forwards to a privileged path",
            "caller identity changes across call frames",
        ],
        "tests": [
            "Map the entry function and every internal call that enforces permissioning.",
            "Attempt the call from an unauthorized actor on a fork or local mirror.",
            "Compare the observed revert / state change against the intended gate.",
        ],
    },
    {
        "name": "State-Difference Probing",
        "match": re.compile(r"account|balance|share|asset|value|mispricing|drift", re.I),
        "why": "If the impact is asset-moving, compare expected vs actual deltas instead of relying on static suspicion.",
        "signals": [
            "asset or share balance mismatch",
            "unexpected accounting drift",
            "state update order differs from the intended flow",
        ],
        "tests": [
            "Snapshot balances / shares before the action.",
            "Execute the candidate path.",
            "Assert the delta matches the intended accounting model.",
        ],
    },
    {
        "name": "Queue and State Transition Review",
        "match": re.compile(r"queue|state machine|state transition|retry|pause|resume|recovery", re.I),
        "why": "Queue and lifecycle bugs usually hide in edge transitions, not in the happy path.",
        "signals": [
            "transition skips a required intermediate state",
            "retry path reuses stale state",
            "cleanup or recovery path leaves residue",
        ],
        "tests": [
            "Enumerate each valid state transition.",
            "Drive the system through the edge transition that the note calls out.",
            "Assert the forbidden state cannot be reached.",
        ],
    },
    {
        "name": "Oracle Delay / Input Validation",
        "match": re.compile(r"oracle|price|stale|delay|feed", re.I),
        "why": "Oracle problems are only real when the protocol accepts bad or stale inputs and then makes a harmful decision.",
        "signals": [
            "stale price accepted",
            "invalid value not rejected",
            "time-delayed input produces a harmful branch",
        ],
        "tests": [
            "Feed stale, zero, or extreme values where the protocol accepts them.",
            "Check whether the downstream action still succeeds.",
            "Measure whether the impact is value-moving or just noisy.",
        ],
    },
    {
        "name": "External Call Ordering",
        "match": re.compile(r"call|callback|delegatecall|low-level|external", re.I),
        "why": "External calls are a bug source when state updates happen after the call or the result is unchecked.",
        "signals": [
            "unchecked return value",
            "state updated after an external call",
            "reentrant or callback path can repeat the action",
        ],
        "tests": [
            "Trace every external call in the candidate path.",
            "Check state-before-call and state-after-call ordering.",
            "Use a fork test to see whether the call can be repeated or bypassed.",
        ],
    },
    {
        "name": "Upgrade / Initialization Review",
        "match": re.compile(r"upgrade|initializer|proxy|implementation|deployment", re.I),
        "why": "Upgrade and initialization bugs usually come from the wrong owner, the wrong init order, or a stale implementation pointer.",
        "signals": [
            "initializer can be called twice",
            "upgrade path lacks authority",
            "implementation state diverges from proxy state",
        ],
        "tests": [
            "Verify who can initialize or upgrade the component.",
            "Check whether initialization can be repeated or skipped.",
            "Compare proxy and implementation storage expectations.",
        ],
    },
    {
        "name": "Rounding / Residual Review",
        "match": re.compile(r"round|dust|residual|precision|fraction", re.I),
        "why": "Rounding bugs need a cumulative or boundary proof; a single small loss is not enough.",
        "signals": [
            "residual balance accumulates",
            "rounding favors one side repeatedly",
            "boundary cases differ from steady-state cases",
        ],
        "tests": [
            "Hit the boundary values and repeated edge cases.",
            "Measure whether residue accumulates across iterations.",
            "Prove whether the residue is exploitable or merely cosmetic.",
        ],
    },
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_markdown(value: str) -> str:
    return re.sub(r"[`*_]+", "", value).strip()


def _extract_target_name(text: str) -> str:
    patterns = [
        r"^#\s+(?P<value>.+)$",
        r"(?im)^##\s+Chosen target\s*\n\s*`(?P<value>[^`]+)`",
        r"(?im)^- Target:\s*`?(?P<value>[^`\n]+)`?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _strip_markdown(match.group("value"))
    return "unnamed target"


def _extract_program(text: str, fallback: str | None = None) -> str:
    match = re.search(r"(?im)^- Program:\s*(?P<value>.+)$", text)
    if match:
        return _strip_markdown(match.group("value"))
    return fallback or ""


def _extract_contract(text: str, fallback: str | None = None) -> str:
    patterns = [
        r"(?im)^##\s+Chosen target\s*\n\s*`(?P<value>[^`]+)`",
        r"(?im)^- Contract:\s*`?(?P<value>[^`\n]+)`?",
        r"(?im)^- Target:\s*`?(?P<value>[^`\n]+)`?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _strip_markdown(match.group("value"))
    return fallback or ""


def _derive_focus(text: str) -> list[dict[str, Any]]:
    focus: list[dict[str, Any]] = []
    for item in HUNT_MODULE_LIBRARY:
        if item["match"].search(text):
            focus.append(
                {
                    "name": item["name"],
                    "why": item["why"],
                    "signals": item["signals"],
                    "tests": item["tests"],
                }
            )
    return focus


def _evidence_requirements() -> list[str]:
    return [
        "A real or production-code-mirror reproduction, not a mocked story.",
        "A complete proof-of-concept command or test.",
        "State snapshots or balance diffs before and after the action.",
        "A signed evidence bundle from ANCHOR.",
        "A short falsifier list that explains what would kill the theory.",
    ]


def _baseline_process() -> list[dict[str, str]]:
    return [
        {"step": "Scope confirmation", "goal": "Verify the target and impact are authorized before spending reproduction effort."},
        {"step": "Hypothesis creation", "goal": "Write one falsifiable claim per suspected mechanism."},
        {"step": "Call-path mapping", "goal": "Trace entry points, internal calls, storage, and external calls."},
        {"step": "Evidence collection", "goal": "Capture traces, state diffs, and relevant source references."},
        {"step": "Fork reproduction", "goal": "Prove or kill the claim on a local fork or code mirror."},
        {"step": "Council review", "goal": "Check scope, impact, alternative explanations, and completeness."},
        {"step": "Archive", "goal": "Keep the hypothesis, repro history, and signed evidence together."},
    ]


def build_hunt_plan(
    *,
    target_path: Path,
    root: Path,
    benchmark_entries: list[dict[str, Any]] | None = None,
    outcome_entries: list[dict[str, Any]] | None = None,
    program: str | None = None,
    contract: str | None = None,
    level: str | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    target_text = _read_text(target_path)
    benchmark_entries = benchmark_entries or []
    outcome_entries = outcome_entries or []

    strategy = compute_strategy(
        benchmark_entries,
        outcome_entries,
        root=root,
        top_n=top_n,
    )
    focus = _derive_focus(target_text)
    target_name = _extract_target_name(target_text)
    selected_contract = contract or _extract_contract(target_text, fallback=target_name)
    selected_program = program or _extract_program(target_text)

    hunt_for = [item["name"] for item in focus] or ["General call-path review"]
    hypothesis_templates = [
        {
            "mechanism": item["name"],
            "claim": (
                f"I think `{selected_contract}` lets an unauthorized actor trigger a protected action because "
                f"the {item['name'].lower()} is not enforced at the actual state-changing boundary."
                if "Authorization" in item["name"]
                else f"I think `{selected_contract}` can be pushed into a harmful edge case because the {item['name'].lower()} is not gated tightly enough."
            ),
            "falsifier": (
                "If the suspected gate is enforced at the real state-changing boundary, this hypothesis dies."
                if "Authorization" in item["name"]
                else "If the action fails under the edge case or leaves no harmful delta, the hypothesis dies."
            ),
        }
        for item in focus[: max(1, len(focus))]
    ]

    if not hypothesis_templates:
        hypothesis_templates = [
            {
                "mechanism": "General call-path review",
                "claim": f"I think `{selected_contract}` has a meaningful bug surface that can be reduced to a falsifiable state transition.",
                "falsifier": "If the candidate path cannot be executed on a fork or does not change state in scope, kill it.",
            }
        ]

    module_order = focus or [
        {
            "name": "Authorization Boundary Review",
            "why": "Start with the most likely bug class for a permissioned target.",
            "signals": ["missing permission gate"],
            "tests": ["trace the gate", "try unauthorized access", "prove the delta"],
        }
    ]

    next_hunt = strategy.get("next_hunt")
    return {
        "schema_version": "1.0",
        "source": "hunt_planner.build_hunt_plan",
        "target": {
            "name": target_name,
            "program": selected_program,
            "contract": selected_contract,
            "level": level or "",
            "path": str(target_path.relative_to(root)) if target_path.is_relative_to(root) else str(target_path),
        },
        "objective": (
            f"Determine whether `{selected_contract}` or its adjacent permissioned path allows an unauthorized or harmful action."
            if selected_contract
            else f"Determine whether {target_name} exposes a reproducible bug path."
        ),
        "hunt_for": hunt_for,
        "focus": focus,
        "hypothesis_templates": hypothesis_templates,
        "module_order": module_order,
        "baseline_process": _baseline_process(),
        "evidence_requirements": _evidence_requirements(),
        "falsifiers": [
            "The actual state-changing boundary blocks unauthorized callers.",
            "The wrapper is only a convenience layer and the gate lives deeper in the permissioned path.",
            "The candidate bug only exists in a mocked setup and does not reproduce on a fork or code mirror.",
        ],
        "next_actions": [
            "Confirm the deployed address and in-scope code before testing.",
            "Map the call chain from entry point to state mutation.",
            "Write a single Foundry test or harness that proves the suspected edge case.",
            "Emit ANCHOR ladder events while the repro runs.",
            "Capture a signed evidence bundle only after the repro is deterministic.",
        ],
        "strategy": strategy,
        "strategy_next_hunt": next_hunt,
        "source_refs": {
            "target_note": str(target_path.relative_to(root)) if target_path.is_relative_to(root) else str(target_path),
            "methodology": "docs/METHODOLOGY.md",
            "proof_gate": "docs/PROOF_GATE.md",
            "bug_map": "BUG_HUNTING_MAP.md",
        },
    }


def render_hunt_plan(payload: dict[str, Any]) -> str:
    target = payload.get("target") or {}
    next_hunt = payload.get("strategy_next_hunt")
    selected_repo = payload.get("selected_repo") or {}
    selection = payload.get("selection") or {}
    if selected_repo or selection:
        lines = [
            "Selected Repo Hunt Plan",
            "",
            f"Repo: {selected_repo.get('full_name', selection.get('repo', '—'))}",
            f"Source run: {selection.get('selected_from_run', '—')}",
            f"Authorization state: {selection.get('authorization_state', 'scope_confirmation_required')}",
            "",
            "Public evidence reviewed",
            "",
        ]
        for item in (selected_repo.get("evidence_sources") or []):
            if isinstance(item, dict):
                label = item.get("note") or item.get("type") or "evidence"
                location = item.get("url") or item.get("path") or ""
                if location:
                    lines.append(f"- {label}: {location}")
                else:
                    lines.append(f"- {label}")
        if not (selected_repo.get("evidence_sources") or []):
            lines.append("- candidate.json")
            lines.append("- summary.md")
            lines.append("- selection.json")

        lines.extend(
            [
                "",
                "Likely code/security surfaces",
                "",
            ]
        )
        for surface in selected_repo.get("likely_surface") or []:
            lines.append(f"- {surface}")
        if not (selected_repo.get("likely_surface") or []):
            lines.append("- unknown")

        lines.extend(
            [
                "",
                "Explicitly excluded until scope confirmation",
                "",
                "- cloning or local analysis",
                "- scanning, fuzzing, or automated test execution",
                "- issue drafting or PR drafting",
                "- contacting maintainers",
                "",
                "Smallest safe next action",
                "",
                "Review SECURITY.md, contribution policy, published program scope, and testing rules.",
                "",
                "Stop conditions",
                "",
                "- repo is outside published scope",
                "- security policy disallows analysis",
                "- selected evidence does not support the named issue angle",
                "- any next step would require intrusive or unauthorized behavior",
                "",
                "Evidence needed before local analysis is allowed",
                "",
                "- published scope or written authorization that covers the repo",
                "- repo security policy reviewed and consistent with the intended work",
                "- a single falsifiable hypothesis tied to the selected evidence",
                "- a minimal, non-intrusive plan for confirming the claim",
            ]
        )
        return "\n".join(lines) + "\n"

    lines = [
        "Hunt Plan",
        "",
        f"Target: {target.get('name', '—')}",
        f"Program: {target.get('program', '—') or '—'}",
        f"Contract: {target.get('contract', '—') or '—'}",
        f"Level: {target.get('level', '—') or '—'}",
        f"Source: {target.get('path', '—')}",
        "",
    ]
    if selected_repo:
        lines.extend(
            [
                "Selected Repo Context",
                "",
                f"- Repo: {selected_repo.get('full_name', '—')}",
                f"- URL: {selected_repo.get('html_url', '—')}",
                f"- Language: {selected_repo.get('language', '—') or '—'}",
                f"- Priority score: {selected_repo.get('priority_score', '—')}/100",
                f"- Review state: {selected_repo.get('review_state', '—')}",
                f"- Suggested posture: {selected_repo.get('suggested_posture', '—')}",
                "",
            ]
        )
    if selection:
        lines.extend(
            [
                "Selection Gate",
                "",
                f"- Selected from run: {selection.get('selected_from_run', '—')}",
                f"- Selected at: {selection.get('selected_at', '—')}",
                f"- Selection status: {selection.get('selection_status', '—')}",
                f"- Authorization state: {selection.get('authorization_state', '—')}",
                f"- Next action: {selection.get('next_action', '—')}",
                "",
            ]
        )

    lines.extend(
        [
            "Objective",
            "",
            payload.get("objective", "—"),
            "",
            "What to hunt for",
            "",
        ]
    )
    for item in payload.get("hunt_for") or []:
        lines.append(f"- {item}")

    lines.extend(["", "How to hunt", ""])
    for step in payload.get("baseline_process") or []:
        lines.append(f"- {step['step']}: {step['goal']}")

    if payload.get("scope_checklist"):
        lines.extend(["", "Scope Checklist", ""])
        for item in payload.get("scope_checklist") or []:
            lines.append(f"- {item}")

    if payload.get("scope_limits"):
        lines.extend(["", "Scope Limits", ""])
        for item in payload.get("scope_limits") or []:
            lines.append(f"- {item}")

    lines.extend(["", "Hypothesis templates", ""])
    for item in payload.get("hypothesis_templates") or []:
        lines.append(f"- Mechanism: {item.get('mechanism', '—')}")
        lines.append(f"  Claim: {item.get('claim', '—')}")
        lines.append(f"  Falsifier: {item.get('falsifier', '—')}")

    lines.extend(["", "Evidence requirements", ""])
    for item in payload.get("evidence_requirements") or []:
        lines.append(f"- {item}")

    lines.extend(["", "Primary falsifiers", ""])
    for item in payload.get("falsifiers") or []:
        lines.append(f"- {item}")

    lines.extend(["", "Module order", ""])
    for item in payload.get("module_order") or []:
        lines.append(f"- {item.get('name', '—')}: {item.get('why', '—')}")

    if next_hunt:
        lines.extend(
            [
                "",
                "Benchmark strategy tie-in",
                "",
                f"- Next benchmark hunt: {next_hunt.get('label', next_hunt.get('challenge', '—'))}",
                f"- Why: {next_hunt.get('reason', '—')}",
                f"- Expected gain: {next_hunt.get('expected_gain', '—')}",
            ]
        )

    lines.extend(
        [
            "",
            "Next actions",
            "",
        ]
    )
    for item in payload.get("next_actions") or []:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "Source refs",
            "",
        ]
    )
    refs = payload.get("source_refs") or {}
    for label, value in refs.items():
        lines.append(f"- {label}: {value}")

    lines.append("")
    return "\n".join(lines)
