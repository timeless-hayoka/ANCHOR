// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

// All protocol imports resolve exclusively to the Sourcify-verified 0.8.18
// source tree. The two minimal mocks below are laboratory dependencies.
import "../../contracts/lendingpool/LendingPool.sol";
import "../../contracts/libraries/helpers/AddressId.sol";

interface VmAnchor {
    function prank(address who) external;
    function startPrank(address who) external;
    function stopPrank() external;
    function expectRevert() external;
    function warp(uint256 time) external;
}

contract AnchorMockERC20 {
    string public name = "ANCHOR isolated reserve";
    string public symbol = "AIR";
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address who, uint256 amount) external {
        balanceOf[who] += amount;
        totalSupply += amount;
    }

    function approve(address to, uint256 amount) external returns (bool) {
        allowance[msg.sender][to] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= amount, "allowance");
        allowance[from][msg.sender] = allowed - amount;
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(balanceOf[from] >= amount, "balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
    }
}

contract AnchorMockRegistry {
    mapping(uint256 => address) internal entries;
    function setAddress(uint256 id, address where) external {
        entries[id] = where;
    }
    function getAddress(uint256 id) external view returns (address) {
        return entries[id];
    }
}

contract AnchorMockVaultFactory {
    mapping(uint256 => address) public vaults;
    function setVault(uint256 id, address who) external {
        vaults[id] = who;
    }
}

/// @notice Checks actual Sourcify-verified Solidity source, compiled with
/// solc 0.8.18. This fixture is not the earlier pinned GitHub revision.
/// Real deployment immutables/storage are not reconstructed or claimed.
contract AnchorVerifiedStatefulTest {
    VmAnchor internal constant vm = VmAnchor(
        address(uint160(uint256(keccak256("hevm cheat code"))))
    );
    AnchorMockRegistry internal registry;
    LendingPool internal pool;
    AnchorMockERC20 internal token;
    AnchorMockVaultFactory internal factory;
    address internal constant ALICE = address(0xA11CE);
    address internal constant BOB = address(0xB0B);
    address internal constant VAULT = address(0xC0FFEE);
    address internal constant WETH = address(0x4200000000000000000000000000000000000006);
    uint256 internal reserveId;

    function setUp() public {
        token = new AnchorMockERC20();
        registry = new AnchorMockRegistry();
        factory = new AnchorMockVaultFactory();
        registry.setAddress(AddressId.ADDRESS_ID_TREASURY, address(0x7EA5));
        registry.setAddress(AddressId.ADDRESS_ID_VAULT_FACTORY, address(factory));
        factory.setVault(1, VAULT);
        pool = new LendingPool(address(registry), WETH);
        pool.initReserve(address(token));
        reserveId = pool.nextReserveId() - 1;
        token.mint(ALICE, 2_000_000);
        token.mint(BOB, 2_000_000);
    }

    function _deposit(address who, uint256 amount) internal returns (uint256 shares) {
        vm.startPrank(who);
        token.approve(address(pool), amount);
        shares = pool.deposit(reserveId, amount, who, 0);
        vm.stopPrank();
    }

    function _balanceShares(address who) internal view returns (uint256) {
        return IERC20(pool.getETokenAddress(reserveId)).balanceOf(who);
    }

    function test_VerifiedFirstTwoDepositorsConserveLiquidity() public {
        uint256 aliceShares = _deposit(ALICE, 100_000);
        uint256 bobShares = _deposit(BOB, 200_000);
        // The verified deployed-source implementation differs from the pinned
        // GitHub revision's initial 1,000-share lock. Do not copy that premise.
        require(aliceShares > 0 && bobShares > 0, "no deposit shares");
        require(_balanceShares(ALICE) == aliceShares, "alice share balance");
        require(_balanceShares(BOB) == bobShares, "bob share balance");
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == 300_000, "reserve liquidity conservation");
        require(token.balanceOf(ALICE) == 1_900_000, "alice reserves");
        require(token.balanceOf(BOB) == 1_800_000, "bob reserves");
    }

    function test_VerifiedUnauthorizedBorrowAndReserveCreationFail() public {
        _deposit(ALICE, 100_000);
        vm.prank(BOB);
        vm.expectRevert();
        pool.initReserve(address(token));
        vm.prank(BOB);
        vm.expectRevert();
        pool.borrow(BOB, 1, 100);
        require(token.balanceOf(BOB) == 2_000_000, "unauthorized balance change");
    }

    function _prepareDebt() internal returns (uint256 debtId) {
        _deposit(ALICE, 500_000);
        pool.enableVaultToBorrow(1);
        pool.setCreditsOfVault(1, reserveId, 200_000);
        vm.prank(VAULT);
        debtId = pool.newDebtPosition(reserveId);
    }

    function test_VerifiedBorrowAndRepayConserveAssetsAndCredit() public {
        uint256 id = _prepareDebt();
        uint256 priorLiquidity = token.balanceOf(pool.getETokenAddress(reserveId));
        vm.prank(VAULT);
        pool.borrow(VAULT, id, 100_000);
        require(token.balanceOf(VAULT) == 100_000, "vault not paid");
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == priorLiquidity - 100_000, "borrow liquidity");
        require(pool.credits(reserveId, VAULT) == 100_000, "borrow credit consumption");
        (uint256 beforeDebt,) = pool.getCurrentDebt(id);
        require(beforeDebt >= 100_000, "borrow debt missing");

        vm.startPrank(VAULT);
        token.approve(address(pool), type(uint256).max);
        uint256 paid = pool.repay(VAULT, id, 100_000);
        vm.stopPrank();
        require(paid > 0 && paid <= 100_000, "invalid repayment");
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == priorLiquidity - 100_000 + paid, "repay liquidity");
        require(pool.credits(reserveId, VAULT) == 100_000 + paid, "repay credit restoration");
        (uint256 afterDebt,) = pool.getCurrentDebt(id);
        require(afterDebt <= beforeDebt, "repay debt increased in same block");
    }

    function test_VerifiedCreditAndDebtOwnerBoundaries() public {
        uint256 id = _prepareDebt();
        vm.prank(BOB);
        vm.expectRevert();
        pool.borrow(BOB, id, 1);
        vm.prank(VAULT);
        vm.expectRevert();
        pool.borrow(VAULT, id, 200_001);
        require(token.balanceOf(VAULT) == 0, "failed borrow transferred tokens");
        require(pool.credits(reserveId, VAULT) == 200_000, "failed borrow consumed credit");
    }

    function testFuzz_VerifiedFirstDepositConservation(uint96 raw) public {
        uint256 amount = 1_001 + (uint256(raw) % 900_000);
        uint256 shares = _deposit(ALICE, amount);
        require(shares > 0, "no minted shares");
        require(_balanceShares(ALICE) == shares, "share recipient mismatch");
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == amount, "underlying conserved");
        require(token.balanceOf(ALICE) == 2_000_000 - amount, "payer debited");
    }

    function testFuzz_VerifiedBorrowRepayCreditConservation(uint96 raw) public {
        uint256 debtId = _prepareDebt();
        uint256 amount = 1_000 + (uint256(raw) % 180_000);
        uint256 initialLiquidity = token.balanceOf(pool.getETokenAddress(reserveId));
        vm.prank(VAULT);
        pool.borrow(VAULT, debtId, amount);
        require(token.balanceOf(VAULT) == amount, "vault borrowed funds");
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == initialLiquidity - amount, "borrow debit");
        require(pool.credits(reserveId, VAULT) == 200_000 - amount, "credit debit");
        vm.startPrank(VAULT);
        token.approve(address(pool), amount);
        uint256 repaid = pool.repay(VAULT, debtId, amount);
        vm.stopPrank();
        require(repaid == amount, "same-block repayment mismatch");
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == initialLiquidity, "repay asset recovery");
        require(pool.credits(reserveId, VAULT) == 200_000, "credit restoration");
        (uint256 outstanding,) = pool.getCurrentDebt(debtId);
        require(outstanding == 0, "same-block debt not extinguished");
    }

    function test_VerifiedPauseRejectsNewDebtAndDepositsUntilResumed() public {
        pool.emergencyPauseAll();
        vm.startPrank(ALICE);
        token.approve(address(pool), 10_000);
        vm.expectRevert();
        pool.deposit(reserveId, 10_000, ALICE, 0);
        vm.expectRevert();
        pool.newDebtPosition(reserveId);
        vm.stopPrank();
        require(token.balanceOf(pool.getETokenAddress(reserveId)) == 0, "paused deposit mutated state");
        pool.unPauseAll();
        require(_deposit(ALICE, 10_000) > 0, "resumed deposit unavailable");
    }

    function test_VerifiedPartialRepaymentPreservesRemainingDebtAndCredit() public {
        uint256 id = _prepareDebt();
        uint256 startingLiquidity = token.balanceOf(pool.getETokenAddress(reserveId));

        vm.prank(VAULT);
        pool.borrow(VAULT, id, 100_000);
        require(pool.credits(reserveId, VAULT) == 100_000, "initial borrow credit");

        vm.startPrank(VAULT);
        token.approve(address(pool), 40_000);
        uint256 firstPaid = pool.repay(VAULT, id, 40_000);
        vm.stopPrank();

        require(firstPaid == 40_000, "partial repayment amount");
        require(pool.credits(reserveId, VAULT) == 140_000, "partial credit restoration");
        require(
            token.balanceOf(pool.getETokenAddress(reserveId)) ==
                startingLiquidity - 60_000,
            "partial repayment reserve balance"
        );
        (uint256 residualDebt,) = pool.getCurrentDebt(id);
        require(residualDebt == 60_000, "partial repayment residual debt");

        vm.startPrank(VAULT);
        token.approve(address(pool), 60_000);
        uint256 finalPaid = pool.repay(VAULT, id, 60_000);
        vm.stopPrank();

        require(finalPaid == 60_000, "final repayment amount");
        (uint256 closedDebt,) = pool.getCurrentDebt(id);
        require(closedDebt == 0, "debt not extinguished");
        require(pool.credits(reserveId, VAULT) == 200_000, "final credit restoration");
        require(
            token.balanceOf(pool.getETokenAddress(reserveId)) == startingLiquidity,
            "recovered liquidity differs"
        );
    }

    function test_VerifiedMissingRepaymentAllowanceRollsBackDebtAndLiquidity() public {
        uint256 id = _prepareDebt();
        vm.prank(VAULT);
        pool.borrow(VAULT, id, 90_000);

        uint256 previousLiquidity = token.balanceOf(pool.getETokenAddress(reserveId));
        uint256 previousCredit = pool.credits(reserveId, VAULT);
        (uint256 previousDebt,) = pool.getCurrentDebt(id);

        vm.prank(VAULT);
        vm.expectRevert();
        pool.repay(VAULT, id, 30_000);

        require(
            token.balanceOf(pool.getETokenAddress(reserveId)) == previousLiquidity,
            "reverted repay altered underlying liquidity"
        );
        require(
            pool.credits(reserveId, VAULT) == previousCredit,
            "reverted repay changed credit"
        );
        (uint256 subsequentDebt,) = pool.getCurrentDebt(id);
        require(subsequentDebt == previousDebt, "reverted repay changed debt");
    }

    function test_VerifiedInterestAccrualThenPartialRepaymentDoesNotRaiseDebt() public {
        uint256 id = _prepareDebt();
        vm.prank(VAULT);
        pool.borrow(VAULT, id, 100_000);

        vm.warp(block.timestamp + 7 days);
        (uint256 accruedDebt, uint256 accruedIndex) = pool.getCurrentDebt(id);
        require(accruedDebt > 100_000, "no seven-day interest accrued");
        require(accruedIndex > 1e18, "borrow index did not grow");

        // One-half of the borrowed principal is intentionally partial, so
        // the test doesn't depend on total-debt settlement rounding behavior.
        vm.startPrank(VAULT);
        token.approve(address(pool), 50_000);
        uint256 paid = pool.repay(VAULT, id, 50_000);
        vm.stopPrank();
        require(paid == 50_000, "interest-sensitive partial repayment failed");

        (uint256 remainingDebt, uint256 afterIndex) = pool.getCurrentDebt(id);
        require(afterIndex >= accruedIndex, "repayment decreased borrow index");
        require(remainingDebt < accruedDebt, "partial repayment did not reduce debt");
        require(remainingDebt > 0, "partial repayment incorrectly closed debt");
    }

    function test_VerifiedFullSettlementAfterInterestUsesAccruedDebt() public {
        uint256 id = _prepareDebt();
        uint256 startingLiquidity = token.balanceOf(pool.getETokenAddress(reserveId));
        vm.prank(VAULT);
        pool.borrow(VAULT, id, 100_000);

        vm.warp(block.timestamp + 7 days);
        (uint256 due,) = pool.getCurrentDebt(id);
        require(due > 100_000, "interest must accrue before settlement");

        // Fund the simulated vault's interest liability in this isolated lab.
        // This is not a source of yield or a production transaction.
        token.mint(VAULT, due - 100_000);
        require(token.balanceOf(VAULT) == due, "vault has insufficient debt repayment assets");

        vm.startPrank(VAULT);
        token.approve(address(pool), due);
        uint256 paid = pool.repay(VAULT, id, due);
        vm.stopPrank();

        require(paid == due, "full accrued debt repayment was not accepted");
        (uint256 remainingDebt,) = pool.getCurrentDebt(id);
        require(remainingDebt == 0, "full settlement left nonzero debt");
        require(token.balanceOf(VAULT) == 0, "vault retained settlement funds");
        require(
            token.balanceOf(pool.getETokenAddress(reserveId)) == startingLiquidity + due - 100_000,
            "reserve liquidity did not receive accrued interest"
        );
    }

    function test_VerifiedBorrowingInterestAccruesOverSevenDays() public {
        uint256 id = _prepareDebt();
        vm.prank(VAULT);
        pool.borrow(VAULT, id, 100_000);
        (uint256 startingDebt, uint256 startingIndex) = pool.getCurrentDebt(id);
        require(pool.borrowingRateOfReserve(reserveId) > 0, "positive utilization must charge interest");
        vm.warp(block.timestamp + 7 days);
        (uint256 laterDebt, uint256 laterIndex) = pool.getCurrentDebt(id);
        require(laterIndex > startingIndex, "borrow index failed to accrue");
        require(laterDebt > startingDebt, "debt failed to accrue at positive rate");
    }
}
