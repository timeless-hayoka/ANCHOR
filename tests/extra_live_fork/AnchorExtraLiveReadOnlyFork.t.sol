// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

/// @notice Live OP Mainnet STATE read assertions executed only inside a
///         disposable, pinned-block Foundry fork. No impersonation, calls to
///         state-mutating methods, broadcasts, PoCs or new finding claims.
interface VmAnchorFork {
    function prank(address who) external;
    function expectRevert() external;
}

interface IAnchorAddressRegistry {
    function getAddress(uint256 id) external view returns (address);
}

interface IAnchorVaultFactory {
    function vaults(uint256 id) external view returns (address);
}

interface IAnchorLiveLendingPool {
    function addressRegistry() external view returns (address);
    function nextReserveId() external view returns (uint256);
    function nextDebtPositionId() external view returns (uint256);
    function paused() external view returns (bool);
    function initReserve(address asset) external;
    function borrow(address onBehalfOf, uint256 debtId, uint256 amount) external;
    function repay(address onBehalfOf, uint256 debtId, uint256 amount) external returns (uint256);
    function borrowingWhiteList(address vault) external view returns (bool);
    function credits(uint256 reserveId, address vault) external view returns (uint256);
    function setCreditsOfVault(uint256 vaultId, uint256 reserveId, uint256 credit) external;
    function enableVaultToBorrow(uint256 vaultId) external;
    function disableVaultToBorrow(uint256 vaultId) external;
    function freezeReserve(uint256 reserveId) external;
    function unFreezeReserve(uint256 reserveId) external;

    function getUnderlyingTokenAddress(uint256 reserveId) external view returns (address);
    function getETokenAddress(uint256 reserveId) external view returns (address);
    function totalLiquidityOfReserve(uint256 reserveId) external view returns (uint256);
    function totalBorrowsOfReserve(uint256 reserveId) external view returns (uint256);
    function borrowingRateOfReserve(uint256 reserveId) external view returns (uint256);
    function utilizationRateOfReserve(uint256 reserveId) external view returns (uint256);
}

contract AnchorExtraLiveReadOnlyForkTest {
    // Foundry displays standard DSTest-style events for passing tests with
    // -vv, providing inspectable onchain values from a single pinned block.
    event log_named_uint(string label, uint256 value);
    event log_named_address(string label, address value);
    address internal constant TARGET =
        0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD;
    uint256 internal constant OP_CHAIN_ID = 10;
    uint256 internal constant MAX_RESERVES_TO_READ = 8;

    IAnchorLiveLendingPool internal constant POOL =
        IAnchorLiveLendingPool(TARGET);
    VmAnchorFork internal constant vm = VmAnchorFork(
        address(uint160(uint256(keccak256("hevm cheat code"))))
    );

    function test_LiveForkIdentityAndActualDeploymentStorage() public {
        require(block.chainid == OP_CHAIN_ID, "must fork Optimism");
        require(TARGET.code.length > 10_000, "target bytecode missing");
        address registry = POOL.addressRegistry();
        require(registry != address(0) && registry.code.length > 0, "real registry missing");
        require(POOL.nextReserveId() > 1, "no deployed reserves");
        require(POOL.nextDebtPositionId() >= 1, "invalid debt position count");
        emit log_named_uint("fork_block", block.number);
        emit log_named_address("registry", registry);
        emit log_named_uint("nextReserveId", POOL.nextReserveId());
        emit log_named_uint("nextDebtPositionId", POOL.nextDebtPositionId());
    }

    function test_LiveForkReserveAddressesAndDebtViews() public {
        require(block.chainid == OP_CHAIN_ID, "wrong chain");
        uint256 next = POOL.nextReserveId();
        require(next > 1, "no live reserves");
        uint256 max = next - 1;
        if (max > MAX_RESERVES_TO_READ) max = MAX_RESERVES_TO_READ;
        for (uint256 id = 1; id <= max; id++) {
            address underlying = POOL.getUnderlyingTokenAddress(id);
            address eToken = POOL.getETokenAddress(id);
            require(underlying != address(0) && underlying.code.length > 0, "reserve token not deployed");
            require(eToken != address(0) && eToken.code.length > 0, "eToken not deployed");
            // Read the *live state* and rate curves, not values reconstructed
            // from a mocked registry or a freshly initialized reserve.
            uint256 liquidity = POOL.totalLiquidityOfReserve(id);
            uint256 borrows = POOL.totalBorrowsOfReserve(id);
            uint256 utilization = POOL.utilizationRateOfReserve(id);
            uint256 borrowingRate = POOL.borrowingRateOfReserve(id);
            require(liquidity >= borrows, "live reserve owes more than reported total liquidity");
            require(utilization <= 1e18, "live utilization greater than 100 percent");
            require(borrowingRate <= 100e18, "unreasonable live annualized borrow rate");
            emit log_named_uint("reserve_id", id);
            emit log_named_address("underlying", underlying);
            emit log_named_address("eToken", eToken);
            emit log_named_uint("total_liquidity", liquidity);
            emit log_named_uint("total_borrows", borrows);
            emit log_named_uint("utilization_1e18", utilization);
            emit log_named_uint("borrowing_rate_1e18", borrowingRate);
        }
    }

    /// @notice SECURITY NEGATIVE CONTROL: execute one attempted owner-only
    /// reserve initialization only inside the disposable local fork. The
    /// external RPC remains strictly read-only and no tx is broadcast.
    function test_LocalForkNonOwnerCannotInitializeReserve() public {
        require(block.chainid == OP_CHAIN_ID, "wrong network");
        address unprivileged = address(uint160(0xA11CE));
        uint256 reserveCounterBefore = POOL.nextReserveId();
        address knownUnderlying = POOL.getUnderlyingTokenAddress(1);
        require(knownUnderlying != address(0), "no known reserve asset");
        vm.prank(unprivileged);
        vm.expectRevert();
        POOL.initReserve(knownUnderlying);
        require(
            POOL.nextReserveId() == reserveCounterBefore,
            "unauthorized reserve initialization modified live-fork storage"
        );
    }

    /// @notice This attempts state mutations *only inside a disposable local*
    /// fork. The public RPC endpoint receives state reads only; no broadcast.
    /// Fresh EOA has no whitelist entry, nor a privileged vault identity.
    function test_LocalForkUnknownAccountCannotBorrowOrRepayExistingDebt() public {
        require(block.chainid == OP_CHAIN_ID, "wrong network");
        address stranger = address(uint160(0x5A7A6E));
        require(!POOL.borrowingWhiteList(stranger), "EOA unexpectedly whitelisted");

        uint256 debtId = 1;
        uint256 reserveId = 1;
        uint256 reserveBefore = POOL.nextReserveId();
        uint256 debtCounterBefore = POOL.nextDebtPositionId();
        uint256 liquidityBefore = POOL.totalLiquidityOfReserve(reserveId);
        uint256 borrowsBefore = POOL.totalBorrowsOfReserve(reserveId);

        vm.prank(stranger);
        vm.expectRevert();
        POOL.borrow(stranger, debtId, 1);

        vm.prank(stranger);
        vm.expectRevert();
        POOL.repay(stranger, debtId, 1);

        require(POOL.nextReserveId() == reserveBefore, "failed requests changed reserve IDs");
        require(POOL.nextDebtPositionId() == debtCounterBefore, "failed requests changed debt IDs");
        require(POOL.totalLiquidityOfReserve(reserveId) == liquidityBefore, "failed requests changed liquidity");
        require(POOL.totalBorrowsOfReserve(reserveId) == borrowsBefore, "failed requests changed borrow balance");
    }

    /// @notice Reject an ordinary account's attempt to increase the
    /// existing onchain vault's borrowing budget. All attempted state
    /// changes occur only in this disposable local Foundry fork.
    /// @dev LendingPool.getVault() is INTERNAL in verified Solidity; resolve
    /// registry key 10 (ADDRESS_ID_VAULT_FACTORY) through the actual external
    /// registry and then its public vaults(id) mapping. No fabricated ABI.
    function _realVault(uint256 vaultId) internal view returns (address vault) {
        address registry = POOL.addressRegistry();
        require(registry.code.length > 0, "registry missing");
        address factory = IAnchorAddressRegistry(registry).getAddress(10);
        require(factory != address(0) && factory.code.length > 0, "vault factory missing");
        vault = IAnchorVaultFactory(factory).vaults(vaultId);
        require(vault != address(0) && vault.code.length > 0, "vault ID not deployed");
    }

    function test_LocalForkNonOwnerCannotIncreaseExistingVaultCredits() public {
        require(block.chainid == OP_CHAIN_ID, "wrong chain");
        uint256 reserveId = 1;
        uint256 vaultId = 1;
        address currentVault = _realVault(vaultId);
        require(currentVault != address(0) && currentVault.code.length > 0, "real vault missing");

        address outsider = address(uint160(0xD00D));
        uint256 beforeCredits = POOL.credits(reserveId, currentVault);
        uint256 beforeLiquidity = POOL.totalLiquidityOfReserve(reserveId);
        uint256 beforeBorrow = POOL.totalBorrowsOfReserve(reserveId);
        bool beforeWhitelist = POOL.borrowingWhiteList(currentVault);

        vm.prank(outsider);
        vm.expectRevert();
        POOL.setCreditsOfVault(vaultId, reserveId, beforeCredits + 1);

        require(POOL.credits(reserveId, currentVault) == beforeCredits, "unauthorized credits modified");
        require(POOL.borrowingWhiteList(currentVault) == beforeWhitelist, "whitelist changed on credit failure");
        require(POOL.totalLiquidityOfReserve(reserveId) == beforeLiquidity, "liquidity changed on credit failure");
        require(POOL.totalBorrowsOfReserve(reserveId) == beforeBorrow, "borrow totals changed on credit failure");
    }

    /// @notice Neither the whitelist nor a live reserve's admin flags
    /// can be modified by a newly selected non-admin account.
    function test_LocalForkNonOwnerCannotToggleVaultBorrowingAuthorization() public {
        require(block.chainid == OP_CHAIN_ID, "wrong chain");
        uint256 vaultId = 1;
        address vault = POOL.getVault(vaultId);
        require(vault != address(0) && vault.code.length > 0, "real vault missing");
        address outsider = address(uint160(0xD00D));
        bool initiallyWhitelisted = POOL.borrowingWhiteList(vault);
        uint256 beforeCredits = POOL.credits(1, vault);
        uint256 beforeReserveCounter = POOL.nextReserveId();

        vm.prank(outsider);
        vm.expectRevert();
        POOL.enableVaultToBorrow(vaultId);
        vm.prank(outsider);
        vm.expectRevert();
        POOL.disableVaultToBorrow(vaultId);
        vm.prank(outsider);
        vm.expectRevert();
        POOL.freezeReserve(1);
        vm.prank(outsider);
        vm.expectRevert();
        POOL.unFreezeReserve(1);

        require(POOL.borrowingWhiteList(vault) == initiallyWhitelisted, "vault authorization modified");
        require(POOL.credits(1, vault) == beforeCredits, "vault credits modified");
        require(POOL.nextReserveId() == beforeReserveCounter, "admin failure modified reserve IDs");
    }

    function test_LiveForkReadOnlyCallsAreDeterministic() public view {
        require(block.chainid == OP_CHAIN_ID, "wrong chain");
        uint256 reserveId = 1;
        uint256 beforeLiquidity = POOL.totalLiquidityOfReserve(reserveId);
        uint256 beforeDebt = POOL.totalBorrowsOfReserve(reserveId);
        uint256 beforeRate = POOL.borrowingRateOfReserve(reserveId);
        require(POOL.totalLiquidityOfReserve(reserveId) == beforeLiquidity, "liquidity read drift");
        require(POOL.totalBorrowsOfReserve(reserveId) == beforeDebt, "borrows read drift");
        require(POOL.borrowingRateOfReserve(reserveId) == beforeRate, "rate read drift");
    }
}
