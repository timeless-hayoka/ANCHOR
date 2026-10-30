// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/WithdrawalLab.sol";

interface Vm { function deal(address account, uint256 newBalance) external; }

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
    Vm private constant vm = Vm(address(uint160(uint256(keccak256('hevm cheat code')))));
    function testVulnerableFixtureReentersTwice() public {
        VulnerableWithdrawal victim = new VulnerableWithdrawal();
        ReentrantProbe probe = new ReentrantProbe(IWithdrawal(address(victim)));
        vm.deal(address(this), 2 ether);
        probe.fund{value: 2 ether}();
        probe.attack();
        require(probe.callbacks() == 2, "vulnerable fixture did not reenter");
        require(address(probe).balance == 2 ether, "unexpected attacker payout");
        require(victim.balances(address(probe)) == 0, "unexpected accounting");
        require(address(victim).balance == 0, "vulnerable fixture did not drain");
    }

    function testPatchedFixtureRejectsNestedWithdrawal() public {
        PatchedWithdrawal victim = new PatchedWithdrawal();
        ReentrantProbe probe = new ReentrantProbe(IWithdrawal(address(victim)));
        vm.deal(address(this), 2 ether);
        probe.fund{value: 2 ether}();
        probe.attack();
        require(probe.callbacks() == 1, "patched fixture permitted reentry");
        require(victim.balances(address(probe)) == 1 ether, "patched accounting incorrect");
        require(address(probe).balance == 1 ether, "unexpected payout");
        require(address(victim).balance == 1 ether, "patched fixture lost extra funds");
    }

    receive() external payable {}
}
