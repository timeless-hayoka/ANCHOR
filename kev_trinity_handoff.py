"""Convert KEV correlations to unprivileged Trinity signal records.

No reproduction, authorization, or vulnerability assertion is implied.
"""
from __future__ import annotations

import hashlib
import json

from trinity_lead_state_machine import LeadRecord, validate_lead


def kev_to_trinity_signals(report: dict) -> list[dict]:
    if not isinstance(report, dict) or not isinstance(report.get("findings"), list):
        raise ValueError("invalid KEV correlation report")
    digest = report.get("catalog_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
        raise ValueError("missing valid catalog digest")
    results = []
    for finding in report["findings"]:
        if not isinstance(finding, dict) or finding.get("status") != "KEV_MATCH_REQUIRES_VALIDATION":
            raise ValueError("unexpected KEV finding status")
        asset, cve = finding.get("asset_id"), finding.get("cve_id")
        if not isinstance(asset, str) or not asset.strip() or not isinstance(cve, str) or not cve.startswith("CVE-"):
            raise ValueError("invalid KEV correlation identity")
        identity = hashlib.sha256(json.dumps([asset, cve], separators=(",", ":")).encode()).hexdigest()[:20]
        lead = LeadRecord(
            lead_id="kev-" + identity,
            target=asset,
            title="KEV correlation requiring validation: " + cve,
            state="signal",
            scope_status="unknown",
            claim="Inventory lists " + cve + "; affected version and exposure unverified",
            evidence_refs=["cisa-kev-sha256:" + digest.lower()],
        )
        errors = validate_lead(lead)
        if errors:
            raise ValueError("Trinity rejected signal: " + "; ".join(errors))
        results.append(lead.to_dict())
    return results
