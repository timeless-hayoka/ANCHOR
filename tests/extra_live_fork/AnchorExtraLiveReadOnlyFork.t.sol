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
