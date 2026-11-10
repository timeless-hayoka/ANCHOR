"""CISA KEV intake and evidence-only inventory correlation.

No version inference: a CVE match is a review candidate, not proof of exposure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def validate_catalog(data: object) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("vulnerabilities"), list):
        raise ValueError("Invalid KEV catalog structure")
    for item in data["vulnerabilities"]:
        if not isinstance(item, dict) or not isinstance(item.get("cveID"), str):
            raise ValueError("Invalid KEV vulnerability record")
        if not item["cveID"].startswith("CVE-"):
            raise ValueError("Invalid CVE identifier")
    return data


def fetch_catalog(timeout: int = 15) -> tuple[dict, str]:
    request = Request(KEV_URL, headers={"User-Agent": "ANCHOR-KEV/0.1"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Unexpected HTTP response")
        raw = response.read(15_000_001)
    if len(raw) > 15_000_000:
        raise ValueError("KEV response exceeds size limit")
    return validate_catalog(json.loads(raw)), hashlib.sha256(raw).hexdigest()


def correlate(catalog: dict, inventory: list[dict]) -> list[dict]:
    """Only correlate explicit CVE IDs supplied by a trusted inventory source."""
    validate_catalog(catalog)
    if not isinstance(inventory, list):
        raise ValueError("Inventory must be a list")
    by_cve = {item["cveID"].upper(): item for item in catalog["vulnerabilities"]}
    findings = []
    for asset in inventory:
        if not isinstance(asset, dict) or not isinstance(asset.get("asset_id"), str):
            raise ValueError("Inventory asset missing asset_id")
        cves = asset.get("verified_cves", [])
        if not isinstance(cves, list) or not all(isinstance(c, str) for c in cves):
            raise ValueError("verified_cves must be a list of CVE strings")
        for cve in sorted(set(c.upper() for c in cves)):
            record = by_cve.get(cve)
            if record:
                findings.append({
                    "asset_id": asset["asset_id"],
                    "cve_id": cve,
                    "status": "KEV_MATCH_REQUIRES_VALIDATION",
                    "evidence": {
                        "vendor": record.get("vendorProject"),
                        "product": record.get("product"),
                        "date_added": record.get("dateAdded"),
                        "required_action": record.get("requiredAction"),
                        "source": KEV_URL,
                    },
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="CISA KEV evidence-only correlator")
    parser.add_argument("--inventory", required=True, type=Path, help="JSON list with asset_id and verified_cves")
    parser.add_argument("--catalog", type=Path, help="Offline CISA KEV JSON; otherwise fetch official feed")
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    if args.catalog:
        raw = args.catalog.read_bytes()
        catalog = validate_catalog(json.loads(raw))
        digest = hashlib.sha256(raw).hexdigest()
    else:
        catalog, digest = fetch_catalog()
    print(json.dumps({
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": KEV_URL,
        "catalog_sha256": digest,
        "findings": correlate(catalog, inventory),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
