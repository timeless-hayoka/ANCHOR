import unittest

from invariant_evidence_gate import evaluate_manifest, self_check


class InvariantEvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "target_ref": "a" * 40,
            "observations": {"total_before": "100", "total_after": "100", "debt": "30", "collateral": "80"},
            "invariants": [
                {"id": "conservation", "left": "total_before", "op": "eq", "right": "total_after"},
                {"id": "solvency", "left": "debt", "op": "lte", "right": "collateral"},
            ],
        }

    def test_self_check(self):
        self_check()

    def test_valid_accounting_and_state(self):
        result = evaluate_manifest(self.manifest)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["validation_state"], "UNVERIFIED_OBSERVATIONS")

    def test_planted_accounting_failure(self):
        self.manifest["observations"]["total_after"] = "99"
        result = evaluate_manifest(self.manifest)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"][0]["status"], "FAIL")

    def test_planted_state_failure(self):
        self.manifest["observations"]["debt"] = "90"
        result = evaluate_manifest(self.manifest)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"][1]["status"], "FAIL")

    def test_reject_missing_observation(self):
        self.manifest["invariants"][0]["left"] = "missing"
        with self.assertRaises(ValueError):
            evaluate_manifest(self.manifest)

    def test_reject_unpinned_target(self):
        self.manifest["target_ref"] = "main"
        with self.assertRaises(ValueError):
            evaluate_manifest(self.manifest)

    def test_reject_float_and_bool(self):
        for value in (1.5, True):
            self.manifest["observations"]["debt"] = value
            with self.assertRaises(ValueError):
                evaluate_manifest(self.manifest)


if __name__ == "__main__":
    unittest.main()
