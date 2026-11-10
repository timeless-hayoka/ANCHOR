# CISA KEV Intelligence — initial intake

This standalone Python module downloads the official CISA Known Exploited
Vulnerabilities JSON feed or reads an offline snapshot, validates its basic
structure, records the SHA-256 of the catalog, and correlates **explicit**
inventory CVE IDs against KEV.

```bash
python -m unittest tests.test_cisa_kev_intelligence -v
python cisa_kev_intelligence.py --inventory inventory.json --catalog kev.json
python cisa_kev_intelligence.py --inventory inventory.json
```

Example inventory (fictional identifiers):
```json
[{"asset_id": "test-server-01", "verified_cves": ["CVE-2025-12345"]}]
```

**Trust boundaries:** Inventory CVEs must be independently verified. Matching a
KEV entry does NOT establish a vulnerable installed version, reachable attack
surface, exploitation, or eligibility for a bounty. No automatic version matching
is attempted; this avoids incorrect string/version comparisons. An inventory
assertion is not independently authenticated by this module. The JSON source is
downloaded over HTTPS, but there is no separate signed-catalog verification.
The digest enables later evidence reconciliation, not source authentication.

Follow-up work: inventory provenance and package identifiers; version-range
matching using ecosystem-aware parsers and advisory data; authenticated source
snapshots; CVE-to-asset evidence; SARIF export; Trinity validation handoff;
cache policy and stale-feed warnings; tests against pinned official fixtures.
