"""Offline tests for bounded source hunk review."""
import importlib.util
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "scripts" / "extra_verified_source_hunk_review.py"
s = importlib.util.spec_from_file_location("extra_hunk_review", p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


class SourceHunkReviewTests(unittest.TestCase):
    def setUp(self):
        self.a = "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd"
        self.snapshot = {
            "chainId": "10", "address": self.a, "runtimeMatch": "match",
            "sources": {"contracts/lendingpool/LendingPool.sol": {
                "content": "contract A {\n  uint x=2;\n}\n"
            }},
        }

    def test_reports_source_change_without_security_claim(self):
        r = m.analyze("contract A {\n  uint x=1;\n}\n", self.snapshot)
        self.assertEqual(r["state"], "SOURCE_DELTA_REVIEW_ONLY")
        self.assertEqual(r["hunk_count"], 1)
        self.assertEqual(r["hunks"][0]["local_excerpt"], ["  uint x=1;"])
        self.assertEqual(r["hunks"][0]["verified_excerpt"], ["  uint x=2;"])
        self.assertFalse(r["same_source_text"])
        self.assertIn("No security impact", r["conclusion"])

    def test_refuses_bad_chain_and_runtime_evidence(self):
        for changed in ({"chainId": "8453"}, {"runtimeMatch": None},
                        {"address": "0x" + "0"*40}, {"sources": {}}):
            with self.subTest(changed=changed):
                self.assertEqual(m.analyze("a", {**self.snapshot, **changed})["state"], "UNVERIFIED")

    def test_bounds_lines_and_hunks(self):
        r = m.bounded_hunks("a\nb\nc\n", "d\ne\nf\n", max_lines=1, max_hunks=1)
        self.assertEqual(r["hunk_count"], 1)
        self.assertEqual(len(r["hunks"][0]["local_excerpt"]), 1)
        self.assertTrue(r["hunks"][0]["truncated"])
