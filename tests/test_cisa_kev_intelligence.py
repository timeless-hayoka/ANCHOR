import unittest
from unittest.mock import patch
from cisa_kev_intelligence import correlate, validate_catalog, fetch_catalog

CATALOG = {"vulnerabilities": [
    {"cveID": "CVE-2025-12345", "vendorProject": "Example", "product": "Widget",
     "dateAdded": "2026-01-01", "requiredAction": "Patch"}]}


class TestKev(unittest.TestCase):
    def test_known_match_is_not_confirmed_exposure(self):
        findings = correlate(CATALOG, [{"asset_id": "a", "verified_cves": ["CVE-2025-12345"]}])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["status"], "KEV_MATCH_REQUIRES_VALIDATION")

    def test_unknown_cve(self):
        self.assertEqual(correlate(CATALOG, [{"asset_id": "a", "verified_cves": ["CVE-2024-00001"]}]), [])

    def test_duplicate_ids_deduplicated(self):
        self.assertEqual(len(correlate(CATALOG, [{"asset_id": "a", "verified_cves":
            ["CVE-2025-12345", "cve-2025-12345"]}])), 1)

    def test_invalid_catalog_rejected(self):
        with self.assertRaises(ValueError):
            validate_catalog({"vulnerabilities": [{"cveID": 1}]})

    def test_invalid_inventory_rejected(self):
        with self.assertRaises(ValueError):
            correlate(CATALOG, [{"asset_id": "a", "verified_cves": "CVE-2025-12345"}])

    def test_no_network_needed_for_offline_correlation(self):
        with patch("cisa_kev_intelligence.urlopen", side_effect=AssertionError("network used")):
            self.assertEqual(len(correlate(CATALOG, [{"asset_id": "a",
                "verified_cves": ["CVE-2025-12345"]}])), 1)


if __name__ == "__main__":
    unittest.main()
