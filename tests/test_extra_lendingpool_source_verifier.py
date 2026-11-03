"""Offline regression tests for fail-closed Extra Finance source verification."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_extra_lendingpool_source.py"
spec = importlib.util.spec_from_file_location("extra_source_verifier", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ExtraSourceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.source = "// SPDX-License-Identifier: MIT\ncontract LendingPool {}\n"
        self.verified = {
            "chainId": "10",
            "address": "0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd",
            "runtimeMatch": "exact_match",
            "sources": {
                "contracts/lendingpool/LendingPool.sol": {"content": self.source},
                "contracts/Payments.sol": {"content": "contract Payments {}"},
            },
        }

    def test_exact_match_is_source_only_not_bytecode_equivalence(self):
        result = verifier.analyze_snapshot(self.verified, self.source)
        self.assertEqual(result["status"], "PINNED_SOURCE_MATCH")
        self.assertIn("full compilation inputs", result["reason"])
        self.assertEqual(result["matched_source_paths"], ["contracts/lendingpool/LendingPool.sol"])

    def test_mismatch_unknown_or_wrong_chain_fail_closed(self):
        cases = [
            {**self.verified, "chainId": "8453"},
            {**self.verified, "address": "0x" + "1" * 40},
            {**self.verified, "runtimeMatch": "match"},
            {**self.verified, "runtimeMatch": None},
            {**self.verified, "sources": {}},
            {**self.verified, "sources": {"contracts/lendingpool/LendingPool.sol": {"content": "different"}}},
            {**self.verified, "sources": {"different.sol": {"content": self.source}}},
            [],
            None,
        ]
        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                self.assertEqual(verifier.analyze_snapshot(snapshot, self.source)["status"], "NOT_VERIFIED")

    def test_offline_cli_never_claims_verification_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "LendingPool.sol"
            snapshot = root / "sourcify.json"
            source.write_text(self.source, encoding="utf-8")
            snapshot.write_text(json.dumps(self.verified), encoding="utf-8")
            self.assertEqual(verifier.main(["--source", str(source), "--snapshot", str(snapshot)]), 0)
            snapshot.write_text("{}", encoding="utf-8")
            self.assertEqual(verifier.main(["--source", str(source), "--snapshot", str(snapshot)]), 2)
            snapshot.write_text("{", encoding="utf-8")
            self.assertEqual(verifier.main(["--source", str(source), "--snapshot", str(snapshot)]), 2)


if __name__ == "__main__":
    unittest.main()
