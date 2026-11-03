#!/usr/bin/env python3
"""Adapt exactly five legacy testFail* tests in an ephemeral upstream checkout.

Never touches the actual ExtraFi GitHub repository, ANCHOR production code, or
the deployed contract. Abort if an upstream test changes unexpectedly.
"""
from __future__ import annotations

import argparse
from pathlib import Path


CASES = {
    "tests/lending-pool/ExtraInterestBearingToken.t.sol": [
        ("testFail_mintByOthers", "test_RevertWhenMintByOthers", "      eToken.mint(\n", "      vm.expectRevert();\n      eToken.mint(\n"),
        ("testFail_BurnByOthers", "test_RevertWhenBurnByOthers", "      eToken.burn(\n", "      vm.expectRevert();\n      eToken.burn(\n"),
    ],
    "tests/lending-pool/LendingPool.t.sol": [
        ("testFail_initReserveByAlice", "test_RevertWhenInitReserveByAlice", None, None),
        ("testFail_depositTooSmall", "test_RevertWhenDepositTooSmall", "      lendingPool.deposit(\n", "      vm.expectRevert();\n      lendingPool.deposit(\n"),
    ],
    "tests/lending-pool/StakingRewards.t.sol": [
        ("testFail_setRewardsByOthers", "test_RevertWhenSetRewardsByOthers", None, None),
    ],
}


def convert_test_file(contents: str, cases: list[tuple[str, str, str | None, str | None]]) -> str:
    """Exact replacement scoped to a legacy function body; fail closed."""
    for old, new, insertion, replacement in cases:
        signature = "function " + old + "("
        if contents.count(signature) != 1 or "function " + new + "(" in contents:
            raise ValueError(f"unexpected test signature: {old}")
        start = contents.index(signature)
        brace = contents.find("{", start)
        if brace < 0:
            raise ValueError(f"missing test body: {old}")
        depth = 0
        end = None
        for i in range(brace, len(contents)):
            if contents[i] == "{":
                depth += 1
            elif contents[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            raise ValueError(f"unterminated test body: {old}")
        body = contents[start:end]
        body = body.replace(signature, "function " + new + "(", 1)
        if old == "testFail_BurnByOthers":
            # The original test fails in its token-balance setup before the
            # access-control assertion. Replace only this ephemeral test body
            # with a focused unauthorized burn call.
            if "udnerlyingToken.mint" not in body or "eToken.burn(" not in body:
                raise ValueError("unexpected original burn-control test")
            body = (
                "function " + new + "() public {\n"
                '    address alice = makeAddr("ALICE");\n'
                "    vm.prank(alice);\n"
                "    vm.expectRevert();\n"
                "    eToken.burn(alice, 1, 1);\n"
                "}"
            )
            insertion = None
        elif old in {"testFail_initReserveByAlice", "testFail_setRewardsByOthers"}:
            stale = 'vm.expectRevert(bytes("Ownable: caller is not the owner !"));'
            if body.count(stale) != 1:
                raise ValueError(f"unexpected Ownable revert expectation: {old}")
            body = body.replace(
                stale, 'vm.expectRevert(bytes("Ownable: caller is not the owner"));'
            )
        if insertion is not None:
            if body.count(insertion) != 1:
                raise ValueError(f"missing expected revert target in: {old}")
            body = body.replace(insertion, replacement, 1)
        else:
            if "vm.expectRevert(" not in body:
                raise ValueError(f"missing existing revert expectation: {old}")
        contents = contents[:start] + body + contents[end:]
    return contents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    # Preflight all transformations before writing any file.
    updates = {}
    for path, cases in CASES.items():
        full = args.checkout / path
        text = full.read_text(encoding="utf-8")
        updates[full] = convert_test_file(text, cases)
    for path, updated in updates.items():
        path.write_text(updated, encoding="utf-8")
    print("Adapted exactly five upstream negative tests in ephemeral checkout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
