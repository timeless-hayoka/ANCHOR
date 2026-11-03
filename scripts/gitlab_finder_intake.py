#!/usr/bin/env python3
"""Normalize public GitLab project metadata into a cautious Finder intake.

This is a passive discovery adapter, NOT a GitHub Finder scan, a verified
code checkout, a bounty scope grant, or an approved target. No network calls.
Export a GitLab list_projects JSON result (list or {data: [...]}), then ingest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

GITLAB_URL = re.compile(r"^https://gitlab\.com/([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)/?$")
MAX_BYTES = 2_000_000
MAX_PROJECTS = 500


def normalize_projects(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list) or len(payload) > MAX_PROJECTS:
        raise ValueError("expected bounded GitLab list_projects array")
    candidates: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    seen: set[str] = set()

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for project in payload:
        if not isinstance(project, dict):
            reject("invalid_item")
            continue
        path, url = project.get("path_with_namespace"), project.get("web_url")
        if not isinstance(path, str) or not isinstance(url, str):
            reject("missing_identity")
            continue
        parsed = GITLAB_URL.fullmatch(url)
        if not parsed or parsed.group(1) != path:
            reject("host_or_identity_mismatch")
            continue
        if project.get("visibility") != "public":
            reject("not_public")
            continue
        if project.get("archived") is not False or project.get("empty_repo") is True:
            reject("archived_or_empty")
            continue
        key = path.casefold()
        if key in seen:
            reject("duplicate")
            continue
        seen.add(key)
        candidate = {
            "host": "gitlab.com",
            "full_name": path,
            "html_url": url,
            "description": str(project.get("description") or "")[:500],
            "last_activity_at": str(project.get("last_activity_at") or ""),
            "visibility": "public",
            "scan_status": "metadata_only",
            "scope_status": "UNCONFIRMED",
            "source_commit": None,
            "onchain_deployment": None,
            "trinity_state": "NOT_CREATED",
            "authorization": "NOT_GRANTED",
            "manual_review_required": True,
        }
        candidates.append(candidate)

    # Score/priority is deliberately absent: no scope or source has been verified.
    candidates.sort(key=lambda row: row["full_name"].casefold())
    return {
        "schema_version": "1.0",
        "provider": "gitlab.com",
        "kind": "passive_public_metadata_intake",
        "candidates": candidates,
        "rejected_counts": rejected,
        "eligible_for_active_testing": False,
        "finder_handoff": "NOT_AUTHORIZED",
        "note": "Read-only metadata: neither bounty eligibility nor Git checkout was verified.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as f:
            raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("metadata exceeds size limit")
        result = normalize_projects(json.loads(raw))
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Do not replace an existing record or reuse a GitHub discovery path.
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
            f.write("\n")
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error)[:180]}))
        return 2
    print(json.dumps({
        "status": "PASSIVE_INTAKE_ONLY",
        "public_candidates": len(result["candidates"]),
        "rejected_counts": result["rejected_counts"],
        "scope_confirmed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
