import unittest
from kev_trinity_handoff import kev_to_trinity_signals


class TestKevTrinityHandoff(unittest.TestCase):
    def setUp(self):
        self.report = {"catalog_sha256": "a" * 64, "findings": [
            {"asset_id": "asset-1", "cve_id": "CVE-2025-12345",
             "status": "KEV_MATCH_REQUIRES_VALIDATION"}]}

    def test_signal_never_claims_reproduction_or_scope(self):
        lead = kev_to_trinity_signals(self.report)[0]
        self.assertEqual(lead["state"], "signal")
        self.assertEqual(lead["scope_status"], "unknown")
        self.assertEqual(lead["watcher_verdict"], "pending")

    def test_deterministic_identity(self):
        self.assertEqual(kev_to_trinity_signals(self.report), kev_to_trinity_signals(self.report))

    def test_reject_promoted_status(self):
        self.report["findings"][0]["status"] = "REPRODUCED_REAL"
        with self.assertRaises(ValueError):
            kev_to_trinity_signals(self.report)

    def test_reject_unpinned_catalog(self):
        self.report["catalog_sha256"] = ""
        with self.assertRaises(ValueError):
            kev_to_trinity_signals(self.report)


if __name__ == "__main__":
    unittest.main()
