"""Regression checks for ephemeral-only legacy ExtraFi test adapter."""
import importlib.util
import unittest
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "scripts" / "extra_legacy_test_adapter.py"
spec = importlib.util.spec_from_file_location("extra_legacy_adapter", script)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class TestLegacyAdapter(unittest.TestCase):
    def test_owner_revert_message_is_updated_only_inside_selected_test(self):
        source = (
            "contract T {\n"
            'function testFail_initReserveByAlice() public {vm.expectRevert(bytes("Ownable: caller is not the owner !"));}\n'
            "function unrelated() public {}\n}"
        )
        converted = adapter.convert_test_file(
            source,
            [adapter.CASES["tests/lending-pool/LendingPool.t.sol"][0]],
        )
        self.assertIn("test_RevertWhenInitReserveByAlice", converted)
        self.assertIn('vm.expectRevert(bytes("Ownable: caller is not the owner"));', converted)
        self.assertIn("function unrelated() public {}", converted)

    def test_unauthorized_burn_becomes_targeted_negative_control(self):
        source = (
            "contract T {\n"
            "function testFail_BurnByOthers() public {\n"
            "udnerlyingToken.mint(address(eToken), 1);\n"
            "eToken.burn(alice, 1, 1);\n"
            "}\n}"
        )
        converted = adapter.convert_test_file(
            source,
            [adapter.CASES["tests/lending-pool/ExtraInterestBearingToken.t.sol"][1]],
        )
        self.assertIn("test_RevertWhenBurnByOthers", converted)
        self.assertIn("vm.expectRevert();", converted)
        self.assertNotIn("udnerlyingToken.mint", converted)
        self.assertIn("eToken.burn(alice, 1, 1);", converted)

    def test_unexpected_upstream_change_is_rejected(self):
        with self.assertRaises(ValueError):
            adapter.convert_test_file(
                "contract T { function unexpected() public {} }",
                [adapter.CASES["tests/lending-pool/LendingPool.t.sol"][0]],
            )


if __name__ == "__main__":
    unittest.main()
