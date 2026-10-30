// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/WithdrawalLab.sol";

interface IWithdrawal {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

contract ReentrantProbe {
    IWithdrawal public target;
    uint256 public callbacks;
    bool public tryAgain;
    constructor(IWithdrawal _target) { target = _target; }
    receive() external payable {
        callbacks++;
        if (tryAgain && callbacks == 1) {
            // The patched implementation rejects this nested withdrawal.
            (bool ok,) = address(target).call(
                abi.encodeWithSelector(IWithdrawal.withdraw.selector, 1 ether)
            );
            if (!ok) tryAgain = false;
        }
    }
    function fund() external payable { target.deposit{value: msg.value}(); }
    function attack() external {
        tryAgain = true;
        target.withdraw(1 ether);
    }
}

contract WithdrawalProofTest {
    function testVulnerableFixtureReentersTwice() public {
        VulnerableWithdrawal victim = new VulnerableWithdrawal();
        ReentrantProbe probe = new ReentrantProbe(IWithdrawal(address(victim)));
        probe.fund{value: 1 ether}();
        probe.attack();
        require(probe.callbacks() == 2, "vulnerable fixture did not reenter");
        require(address(probe).balance == 1 ether, "unexpected attacker payout");
        require(victim.balances(address(probe)) == 0, "unexpected accounting");
    }

    function testPatchedFixtureRejectsNestedWithdrawal() public {
        PatchedWithdrawal victim = new PatchedWithdrawal();
        ReentrantProbe probe = new ReentrantProbe(IWithdrawal(address(victim)));
        probe.fund{value: 1 ether}();
        probe.attack();
        require(probe.callbacks() == 1, "patched fixture permitted reentry");
        require(victim.balances(address(probe)) == 0, "patched balance not cleared");
        require(address(probe).balance == 1 ether, "unexpected payout");
    }

    receive() external payable {}
}
