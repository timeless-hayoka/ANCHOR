// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

/// @notice Live OP Mainnet STATE read assertions executed only inside a
///         disposable, pinned-block Foundry fork. No impersonation, calls to
///         state-mutating methods, broadcasts, PoCs or new finding claims.
interface IAnchorLiveLendingPool {
    function addressRegistry() external view returns (address);
    function nextReserveId() external view returns (uint256);
    function nextDebtPositionId() external view returns (uint256);
    function paused() external view returns (bool);
    function getUnderlyingTokenAddress(uint256 reserveId) external view returns (address);
    function getETokenAddress(uint256 reserveId) external view returns (address);
    function totalLiquidityOfReserve(uint256 reserveId) external view returns (uint256);
    function totalBorrowsOfReserve(uint256 reserveId) external view returns (uint256);
    function borrowingRateOfReserve(uint256 reserveId) external view returns (uint256);
    function utilizationRateOfReserve(uint256 reserveId) external view returns (uint256);
}

contract AnchorExtraLiveReadOnlyForkTest {
    address internal constant TARGET =
        0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd;
    uint256 internal constant OP_CHAIN_ID = 10;
    uint256 internal constant MAX_RESERVES_TO_READ = 8;

    IAnchorLiveLendingPool internal constant POOL =
        IAnchorLiveLendingPool(TARGET);

    function test_LiveForkIdentityAndActualDeploymentStorage() public view {
        require(block.chainid == OP_CHAIN_ID, "must fork Optimism");
        require(TARGET.code.length > 10_000, "target bytecode missing");
        address registry = POOL.addressRegistry();
        require(registry != address(0) && registry.code.length > 0, "real registry missing");
        require(POOL.nextReserveId() > 1, "no deployed reserves");
        require(POOL.nextDebtPositionId() >= 1, "invalid debt position count");
    }

    function test_LiveForkReserveAddressesAndDebtViews() public view {
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
        }
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
