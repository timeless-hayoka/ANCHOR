from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
WORK_QUEUE_PATH = ROOT / "docs" / "ANCHOR_WORK_QUEUE.md"

SECTION_RE = re.compile(r"^##\s+(?P<section>.+?)\s*$")
ITEM_RE = re.compile(r"^###\s+(?P<id>[A-Z]-\d{3})\s+[—-]\s+(?P<title>.+?)\s*$")

LIST_FIELDS = {"acceptance_criteria", "evidence_required", "evidence", "blocked_by"}
TEXT_FIELDS = {"goal", "why_it_matters", "next_smallest_action"}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_block(lines: list[str]) -> str:
    if not lines:
        return ""
    text = "\n".join(lines).strip()
    return text


def _new_item(section: str, item_id: str, title: str) -> dict[str, Any]:
    return {
        "section": section,
        "id": item_id,
        "title": title,
        "status": "",
        "goal": "",
        "why_it_matters": "",
        "acceptance_criteria": [],
        "evidence_required": [],
        "evidence": [],
        "next_smallest_action": "",
        "blocked_by": [],
        "_field_buffer": [],
        "_current_field": None,
    }


def _finalize_item(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    field = item.pop("_current_field", None)
    buffer = item.pop("_field_buffer", [])
    if field in TEXT_FIELDS:
        item[field] = _normalize_block(buffer)
    elif field in LIST_FIELDS:
        item[field] = [line for line in buffer if line]
    return item


def _flush_field(item: dict[str, Any], field: str | None) -> None:
    if not field:
        return
    buffer = item.get("_field_buffer", [])
    if field in TEXT_FIELDS:
        item[field] = _normalize_block(buffer)
    elif field in LIST_FIELDS:
        item[field] = [line for line in buffer if line]
    item["_field_buffer"] = []
    item["_current_field"] = None


def _set_field(item: dict[str, Any], field: str | None) -> None:
    _flush_field(item, item.get("_current_field"))
    item["_current_field"] = field
    item["_field_buffer"] = []


def load_work_queue(path: Path | None = None) -> dict[str, Any]:
    candidate = path or WORK_QUEUE_PATH
    if not candidate.exists():
        return {
            "schema_version": "1.0",
            "kind": "anchor.work_queue",
            "queue_path": str(candidate),
            "updated_at": "",
            "sections": [],
            "items": [],
            "counts": {"active": 0, "ready": 0, "blocked": 0, "completed": 0, "total": 0},
            "summary": "No work queue file found.",
            "top_item": None,
            "next_action": "",
        }

    lines = candidate.read_text(encoding="utf-8").splitlines()
    sections: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    current_item: dict[str, Any] | None = None

    def finish_item() -> None:
        nonlocal current_item
        if current_item is None:
            return
        _flush_field(current_item, current_item.get("_current_field"))
        finalized = _finalize_item(current_item)
        if finalized is not None:
            finalized["status"] = finalized.get("status") or finalized["section"].upper()
            items.append(finalized)
            if current_section is not None:
                current_section.setdefault("items", []).append(finalized)
        current_item = None

    for raw_line in lines:
        line = raw_line.rstrip()
        section_match = SECTION_RE.match(line)
        if section_match and not line.startswith("###"):
            section_name = section_match.group("section").strip()
            if section_name in {"Active", "Ready", "Blocked", "Completed"}:
                finish_item()
                current_section = {
                    "name": section_name,
                    "slug": section_name.lower(),
                    "items": [],
                }
                sections.append(current_section)
                continue

        item_match = ITEM_RE.match(line)
        if item_match:
            finish_item()
            if current_section is None:
                current_section = {"name": "Uncategorized", "slug": "uncategorized", "items": []}
                sections.append(current_section)
            current_item = _new_item(current_section["name"], item_match.group("id").strip(), item_match.group("title").strip())
            continue

        if current_item is None:
            continue

        stripped = line.strip()
        if not stripped:
            current_item.setdefault("_field_buffer", []).append("")
            continue

        if stripped.startswith("**Status:**"):
            current_item["status"] = stripped.removeprefix("**Status:**").strip().strip("*")
            continue
        if stripped == "**Goal**":
            _set_field(current_item, "goal")
            continue
        if stripped == "**Why it matters**":
            _set_field(current_item, "why_it_matters")
            continue
        if stripped == "**Acceptance criteria**":
            _set_field(current_item, "acceptance_criteria")
            continue
        if stripped in {"**Evidence required**", "**Evidence**"}:
            _set_field(current_item, "evidence_required" if stripped == "**Evidence required**" else "evidence")
            continue
        if stripped == "**Next smallest action**":
            _set_field(current_item, "next_smallest_action")
            continue
        if stripped == "**Blocked by**":
            _set_field(current_item, "blocked_by")
            continue

        current_field = current_item.get("_current_field")
        if current_field in LIST_FIELDS:
            if stripped.startswith(("* [ ] ", "- [ ] ", "* [x] ", "- [x] ", "* ", "- ")):
                cleaned = stripped
                for prefix in ("* [ ] ", "- [ ] ", "* [x] ", "- [x] ", "* ", "- "):
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                        break
                current_item.setdefault("_field_buffer", []).append(cleaned)
            continue
        if current_field in TEXT_FIELDS:
            current_item.setdefault("_field_buffer", []).append(line)

    finish_item()

    counts = {
        "active": len(next((section["items"] for section in sections if section["name"] == "Active"), [])),
        "ready": len(next((section["items"] for section in sections if section["name"] == "Ready"), [])),
        "blocked": len(next((section["items"] for section in sections if section["name"] == "Blocked"), [])),
        "completed": len(next((section["items"] for section in sections if section["name"] == "Completed"), [])),
        "total": len(items),
    }

    top_item = None
    for section_name in ("Active", "Ready", "Blocked", "Completed"):
        section = next((sec for sec in sections if sec["name"] == section_name and sec.get("items")), None)
        if section and section["items"]:
            top_item = section["items"][0]
            break
    next_action = top_item.get("next_smallest_action", "") if top_item else ""

    summary = (
        f"{counts['active']} active, {counts['ready']} ready, {counts['blocked']} blocked, "
        f"{counts['completed']} completed"
    )

    return {
        "schema_version": "1.0",
        "kind": "anchor.work_queue",
        "queue_path": str(candidate.relative_to(ROOT)) if candidate.is_relative_to(ROOT) else str(candidate),
        "updated_at": datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc).isoformat(),
        "sections": sections,
        "items": items,
        "counts": counts,
        "summary": summary,
        "top_item": top_item,
        "next_action": next_action,
    }


def work_queue_summary(queue: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = queue or load_work_queue()
    counts = payload.get("counts") or {}
    return {
        "schema_version": payload.get("schema_version", "1.0"),
        "kind": payload.get("kind", "anchor.work_queue"),
        "queue_path": payload.get("queue_path", str(WORK_QUEUE_PATH)),
        "updated_at": payload.get("updated_at", ""),
        "counts": {
            "active": int(counts.get("active", 0) or 0),
            "ready": int(counts.get("ready", 0) or 0),
            "blocked": int(counts.get("blocked", 0) or 0),
            "completed": int(counts.get("completed", 0) or 0),
            "total": int(counts.get("total", 0) or 0),
        },
        "summary": payload.get("summary", ""),
        "sections": payload.get("sections", []),
        "items": payload.get("items", []),
        "top_item": payload.get("top_item"),
        "next_action": payload.get("next_action", ""),
    }


def _wrap_lines(prefix: str, text: str, *, width: int = 88) -> list[str]:
    if not text:
        return []
    import textwrap

    wrapped = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if not wrapped:
        return []
    lines = [f"{prefix}{wrapped[0]}"]
    lines.extend(f"{' ' * len(prefix)}{line}" for line in wrapped[1:])
    return lines


def render_work_queue(queue: dict[str, Any] | None = None) -> str:
    payload = work_queue_summary(queue)
    lines = [
        "ANCHOR Work Queue",
        f"Source: {payload.get('queue_path', str(WORK_QUEUE_PATH))}",
        f"Updated: {payload.get('updated_at') or 'unknown'}",
        f"Counts: {payload['counts']['active']} active · {payload['counts']['ready']} ready · {payload['counts']['blocked']} blocked · {payload['counts']['completed']} completed",
        "",
    ]

    for section in payload.get("sections", []):
        items = section.get("items", []) or []
        lines.append(f"{section.get('name', 'Section')} ({len(items)})")
        if not items:
            lines.append("  (none)")
            lines.append("")
            continue
        for item in items:
            lines.append(f"- {item.get('id', '—')} [{item.get('status') or section.get('name', '—').upper()}] {item.get('title', 'Untitled')}")
            lines.extend(_wrap_lines("  Goal: ", item.get("goal", "")))
            lines.extend(_wrap_lines("  Why: ", item.get("why_it_matters", "")))
            if item.get("acceptance_criteria"):
                lines.append("  Acceptance criteria:")
                lines.extend(f"    - {criterion}" for criterion in item.get("acceptance_criteria", []))
            if item.get("evidence_required"):
                lines.append("  Evidence required:")
                lines.extend(f"    - {evidence}" for evidence in item.get("evidence_required", []))
            if item.get("evidence"):
                lines.append("  Evidence:")
                lines.extend(f"    - {evidence}" for evidence in item.get("evidence", []))
            next_action = item.get("next_smallest_action", "").strip()
            if next_action:
                lines.append("  Next smallest action:")
                for next_line in next_action.splitlines():
                    lines.append(f"    {next_line}")
            if item.get("blocked_by"):
                lines.append("  Blocked by:")
                lines.extend(f"    - {blocked}" for blocked in item.get("blocked_by", []))
            lines.append("")

    top_item = payload.get("top_item") or {}
    if top_item:
        lines.append(f"Top item: {top_item.get('id', '—')} — {top_item.get('title', '—')}")
        next_action = payload.get("next_action", "").strip()
        if next_action:
            lines.append("Next action:")
            for line in next_action.splitlines():
                lines.append(f"  {line}")
    else:
        lines.append("Top item: none")
    return "\n".join(lines).rstrip() + "\n"
