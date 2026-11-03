// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import {Test} from "forge-std/Test.sol";
import "../../contracts/address-registry/AddressRegistry.sol";
import "../../contracts/tokens/MockedMintableERC20.sol";
import "../../contracts/lendingpool/LendingPool.sol";
import {ExtraInterestBearingToken as EToken} from "../../contracts/lendingpool/ExtraInterestBearingToken.sol";

/// @notice Stateful economic baseline for the PINNED ExtraFi repo revision.
/// @dev This is intentionally not a deployed-Sourcify-code equivalence claim.
///      No RPC, fork, live interactions or external test targets.
contract AnchorStatefulLendingPoolTest is Test {
    AddressRegistry private registry;
    LendingPool private pool;
    MockedMintableERC20 private reserve;
    EToken private eToken;
    address private alice;
    address private bob;
    uint256 private reserveId;

    address constant WETH = 0x4200000000000000000000000000000000000006;

    function setUp() public {
        alice = makeAddr("anchor-alice");
        bob = makeAddr("anchor-bob");
        registry = new AddressRegistry(WETH);
        registry.setAddress(AddressId.ADDRESS_ID_TREASURY, makeAddr("treasury"));
        pool = new LendingPool(address(registry), WETH);
        reserve = new MockedMintableERC20("ANCHOR-LAB", "ALAB");
        pool.initReserve(address(reserve));
        reserveId = pool.nextReserveId() - 1;
        eToken = EToken(pool.getETokenAddress(reserveId));
        reserve.mint(alice, 1_000_000);
        reserve.mint(bob, 1_000_000);
    }

    function _deposit(address user, uint256 amount) internal returns (uint256 received) {
        vm.startPrank(user);
        reserve.approve(address(pool), amount);
        received = pool.deposit(reserveId, amount, user, 0);
        vm.stopPrank();
    }

    function _redeem(address user, uint256 shares) internal returns (uint256 assets) {
        vm.startPrank(user);
        eToken.approve(address(pool), shares);
        assets = pool.redeem(reserveId, shares, user, false);
        vm.stopPrank();
    }

    function test_MultiUserDepositPreservesShareAndAssetAccounting() public {
        uint256 aliceShares = _deposit(alice, 100_000);
        uint256 bobShares = _deposit(bob, 200_000);
        assertEq(aliceShares, 99_000, "first depositor share lock mismatch");
        assertEq(bobShares, 200_000, "second depositor shares mismatch");
        assertEq(eToken.balanceOf(alice), aliceShares);
        assertEq(eToken.balanceOf(bob), bobShares);
        assertEq(eToken.totalSupply(), 300_000, "unexpected aggregate shares");
        assertEq(reserve.balanceOf(address(eToken)), 300_000, "assets not conserved");
        assertEq(reserve.balanceOf(alice), 900_000, "alice deposit not debited");
        assertEq(reserve.balanceOf(bob), 800_000, "bob deposit not debited");
    }

    function test_RedeemReturnsOnlyOwnedSharesAndPreservesLockedDust() public {
        uint256 aliceShares = _deposit(alice, 100_000);
        uint256 bobShares = _deposit(bob, 200_000);
        uint256 aliceRecovered = _redeem(alice, aliceShares);
        uint256 bobRecovered = _redeem(bob, bobShares);
        assertEq(aliceRecovered, aliceShares);
        assertEq(bobRecovered, bobShares);
        assertEq(eToken.balanceOf(alice), 0);
        assertEq(eToken.balanceOf(bob), 0);
        assertEq(eToken.totalSupply(), 1000, "locked initial shares must remain");
        assertEq(reserve.balanceOf(address(eToken)), 1000, "locked reserve dust must remain");
        assertEq(reserve.balanceOf(alice), 900_000 + aliceRecovered);
        assertEq(reserve.balanceOf(bob), 800_000 + bobRecovered);
    }

    function test_NonOwnerCannotInitializeAdditionalReserve() public {
        MockedMintableERC20 extra = new MockedMintableERC20("MORE", "MORE");
        vm.prank(alice);
        vm.expectRevert();
        pool.initReserve(address(extra));
        assertEq(pool.nextReserveId(), reserveId + 1, "unauthorized reserve created");
    }

    function test_NoAllowanceCannotSpendOtherUsersReserve() public {
        vm.prank(alice);
        vm.expectRevert();
        pool.deposit(reserveId, 100_000, alice, 0);
        assertEq(reserve.balanceOf(address(eToken)), 0);
        assertEq(eToken.totalSupply(), 0);
    }

    function test_ThirdPartyCannotRedeemAliceSharesWithoutApproval() public {
        uint256 shares = _deposit(alice, 100_000);
        vm.prank(bob);
        vm.expectRevert();
        pool.redeem(reserveId, shares, bob, false);
        assertEq(eToken.balanceOf(alice), shares);
        assertEq(reserve.balanceOf(address(eToken)), 100_000);
    }
}
