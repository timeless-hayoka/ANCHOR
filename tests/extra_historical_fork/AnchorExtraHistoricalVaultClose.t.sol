// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

/// @notice STRICT positive-control attempt against a verified active
/// historical position. This test is scoped only to Optimism block
/// 120000000, VaultFactory vault #3 and position #16.
/// ALL state changes occur inside a disposable Foundry fork; never broadcast.
interface VmAnchorHistorical {
    function prank(address who) external;
}
interface IHistoryRegistry {
    function getAddress(uint256 id) external view returns (address);
}
interface IHistoryFactory {
    function vaults(uint256 id) external view returns (address);
}
interface IHistoryPool {
    function addressRegistry() external view returns (address);
    function nextReserveId() external view returns (uint256);
    function getUnderlyingTokenAddress(uint256 id) external view returns (address);
    function getETokenAddress(uint256 id) external view returns (address);
    function totalLiquidityOfReserve(uint256 id) external view returns (uint256);
    function totalBorrowsOfReserve(uint256 id) external view returns (uint256);
}
interface IHistoryVaultTokens {
    function token0() external view returns (address);
    function token1() external view returns (address);
}
interface IHistoryToken {
    function balanceOf(address account) external view returns (uint256);
}
interface IHistoryManagerClose {
    struct CloseParams {
        uint256 vaultId;
        uint256 vaultPositionId;
        uint16 percent;
        address receiver;
        bool receiveNativeETH;
        uint8 receiveType;
        uint256 minAmount0WhenRemoveLiquidity;
        uint256 minAmount1WhenRemoveLiquidity;
        uint256 deadline;
        uint256 swapExecutorId;
        bytes swapPath;
    }
    function closeVaultPositionPartially(CloseParams calldata p) external;
}
contract AnchorExtraHistoricalVaultCloseTest {
    event log_named_address(string key, address value);
    event log_named_uint(string key, uint256 value);
    event log_named_bytes(string key, bytes value);
    event log_named_bytes32(string key, bytes32 value);
    address constant LENDING_POOL = 0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD;
    uint256 constant TARGET_BLOCK = 120000000;
    uint256 constant VAULT_ID = 3;
    uint256 constant POSITION_ID = 16;
    VmAnchorHistorical constant vm = VmAnchorHistorical(
        address(uint160(uint256(keccak256("hevm cheat code"))))
    );

    function _readPosition(address manager) internal view returns (bytes memory result) {
        (bool ok, bytes memory value) = manager.staticcall(
            abi.encodeWithSignature("getVaultPosition(uint256,uint256)", VAULT_ID, POSITION_ID)
        );
        require(ok && value.length >= 19 * 32, "historical position not readable");
        return value;
    }

    function _word(bytes memory raw, uint256 index) internal pure returns (uint256 value) {
        require(raw.length >= (index + 1) * 32, "position ABI incomplete");
        assembly {
            value := mload(add(add(raw, 32), mul(index, 32)))
        }
    }

    struct ReserveSnapshot {
        uint256 id;
        uint256 realCash;
        uint256 accruedDebt;
        uint256 totalLiquidity;
    }

    /// @dev Independently read eToken custody cash from real ERC20 contract.
    /// This is distinct from trusting LendingPool's liquidity getter alone.
    function _reserveSnapshot(uint256 reserveId) internal view
        returns (ReserveSnapshot memory snap)
    {
        IHistoryPool pool = IHistoryPool(LENDING_POOL);
        address token = pool.getUnderlyingTokenAddress(reserveId);
        address eToken = pool.getETokenAddress(reserveId);
        require(token.code.length > 0 && eToken.code.length > 0, "sampled reserve missing");
        snap.id = reserveId;
        snap.realCash = IHistoryToken(token).balanceOf(eToken);
        snap.accruedDebt = pool.totalBorrowsOfReserve(reserveId);
        snap.totalLiquidity = pool.totalLiquidityOfReserve(reserveId);
        require(
            snap.totalLiquidity >= snap.accruedDebt &&
            snap.totalLiquidity - snap.accruedDebt == snap.realCash,
            "independent custody cash/debt invariant violated"
        );
    }

    function _matchedReserves(address token0, address token1)
        internal view returns (uint256[2] memory matched)
    {
        IHistoryPool pool = IHistoryPool(LENDING_POOL);
        uint256 upper = pool.nextReserveId();
        // Only a bounded scan to stay within the public archival RPC budget.
        if (upper > 17) upper = 17;
        for (uint256 id = 1; id < upper; ++id) {
            address underlying = pool.getUnderlyingTokenAddress(id);
            if (underlying == token0) matched[0] = id;
            if (underlying == token1) matched[1] = id;
        }
    }

    function _assertMatchedReserveAccounting(uint256[2] memory matched, string memory phase)
        internal
    {
        for (uint256 i = 0; i < 2; ++i) {
            if (matched[i] == 0) continue;
            ReserveSnapshot memory snap = _reserveSnapshot(matched[i]);
            emit log_named_uint(string(abi.encodePacked(phase, "_reserve_id")), snap.id);
            emit log_named_uint(string(abi.encodePacked(phase, "_cash")), snap.realCash);
            emit log_named_uint(string(abi.encodePacked(phase, "_accrued_debt")), snap.accruedDebt);
            emit log_named_uint(string(abi.encodePacked(phase, "_total")), snap.totalLiquidity);
        }
    }

    function test_HistoricalRecordedManagerCanClosePartOfRealActivePosition() public {
        require(block.chainid == 10 && block.number == TARGET_BLOCK, "not pinned historical OP fork");
        require(LENDING_POOL.code.length > 0, "LendingPool did not exist");
        address registry = IHistoryPool(LENDING_POOL).addressRegistry();
        address factory = IHistoryRegistry(registry).getAddress(10);
        address positionManager = IHistoryRegistry(registry).getAddress(7);
        require(positionManager.code.length > 0, "manager contract unavailable");
        address vault = IHistoryFactory(factory).vaults(VAULT_ID);
        require(vault.code.length > 0, "deployed vault unavailable");
        (bool vaultBeforeOk, bytes memory vaultBefore) =
            vault.staticcall(abi.encodeWithSignature("getVaultState()"));
        require(vaultBeforeOk && vaultBefore.length > 0, "historical vault state unreadable");
        emit log_named_bytes32("BEFORE_VAULT_STATE_HASH", keccak256(vaultBefore));
        address underlying0 = IHistoryVaultTokens(vault).token0();
        address underlying1 = IHistoryVaultTokens(vault).token1();
        require(underlying0.code.length > 0 && underlying1.code.length > 0, "vault token code missing");
        uint256[2] memory matched = _matchedReserves(underlying0, underlying1);
        require(matched[0] != 0 && matched[1] != 0 && matched[0] != matched[1],
            "actual vault asset reserves missing from bounded sample");
        ReserveSnapshot memory token0BeforeReserve = _reserveSnapshot(matched[0]);
        ReserveSnapshot memory token1BeforeReserve = _reserveSnapshot(matched[1]);
        uint256 vaultToken0Before = IHistoryToken(underlying0).balanceOf(vault);
        uint256 vaultToken1Before = IHistoryToken(underlying1).balanceOf(vault);
        emit log_named_address("HISTORICAL_TOKEN0", underlying0);
        emit log_named_address("HISTORICAL_TOKEN1", underlying1);
        emit log_named_uint("BEFORE_VAULT_TOKEN0", vaultToken0Before);
        emit log_named_uint("BEFORE_VAULT_TOKEN1", vaultToken1Before);
        _assertMatchedReserveAccounting(matched, "BEFORE");

        bytes memory beforePosition = _readPosition(positionManager);
        address recordedManager = address(uint160(_word(beforePosition, 0)));
        require(recordedManager != address(0), "position has no recorded manager");
        require(_word(beforePosition, 1) == 1, "position is not active at pinned block");
        uint256 liquidityBefore = _word(beforePosition, 12);
        uint256 debt0Before = _word(beforePosition, 13);
        uint256 debt1Before = _word(beforePosition, 14);
        require(liquidityBefore > 0, "no collateral liquidity");
        require(debt0Before + debt1Before > 0, "not a debt-bearing position");

        emit log_named_address("ACTUAL_MANAGER", recordedManager);
        emit log_named_uint("BEFORE_LIQUIDITY", liquidityBefore);
        emit log_named_uint("BEFORE_DEBT0", debt0Before);
        emit log_named_uint("BEFORE_DEBT1", debt1Before);
        emit log_named_bytes32("BEFORE_POSITION_HASH", keccak256(beforePosition));

        IHistoryManagerClose.CloseParams memory params = IHistoryManagerClose.CloseParams({
            vaultId: VAULT_ID,
            vaultPositionId: POSITION_ID,
            percent: 1000, // 10% of position under 10000 basis point convention
            receiver: recordedManager,
            receiveNativeETH: false,
            receiveType: 2,
            minAmount0WhenRemoveLiquidity: 0,
            minAmount1WhenRemoveLiquidity: 0,
            deadline: block.timestamp + 1 hours,
            swapExecutorId: 0,
            swapPath: new bytes(0)
        });

        // Owner/manager identity is simulated in the local fork only.
        vm.prank(recordedManager);
        (bool succeeded, bytes memory returndata) = positionManager.call(
            abi.encodeWithSelector(IHistoryManagerClose.closeVaultPositionPartially.selector, params)
        );
        if (!succeeded) {
            emit log_named_bytes("HISTORICAL_CLOSE_REVERT_DATA", returndata);
            revert("authorized historical close did not succeed; no finding implied");
        }

        bytes memory afterPosition = _readPosition(positionManager);
        emit log_named_bytes32("AFTER_POSITION_HASH", keccak256(afterPosition));
        emit log_named_uint("AFTER_LIQUIDITY", _word(afterPosition, 12));
        emit log_named_uint("AFTER_DEBT0", _word(afterPosition, 13));
        emit log_named_uint("AFTER_DEBT1", _word(afterPosition, 14));
        require(keccak256(afterPosition) != keccak256(beforePosition), "successful close did not alter position");
        require(address(uint160(_word(afterPosition, 0))) == recordedManager, "position manager changed");
        require(_word(afterPosition, 1) == 1, "10 percent close unexpectedly deactivated position");
        require(_word(afterPosition, 5) <= _word(beforePosition, 5), "principal0 increased after close");
        require(_word(afterPosition, 6) <= _word(beforePosition, 6), "principal1 increased after close");
        require(_word(afterPosition, 12) < liquidityBefore, "partial close did not reduce liquidity");
        require(_word(afterPosition, 13) <= debt0Before, "debt0 unexpectedly increased");
        require(_word(afterPosition, 14) < debt1Before, "debt1 did not decrease");
        (bool vaultAfterOk, bytes memory vaultAfter) =
            vault.staticcall(abi.encodeWithSignature("getVaultState()"));
        require(vaultAfterOk && vaultAfter.length > 0, "post-close vault state unavailable");
        emit log_named_bytes32("AFTER_VAULT_STATE_HASH", keccak256(vaultAfter));
        require(keccak256(vaultBefore) != keccak256(vaultAfter), "close did not change vault state");
        emit log_named_uint("AFTER_VAULT_TOKEN0", IHistoryToken(underlying0).balanceOf(vault));
        emit log_named_uint("AFTER_VAULT_TOKEN1", IHistoryToken(underlying1).balanceOf(vault));
        _assertMatchedReserveAccounting(matched, "AFTER");
        ReserveSnapshot memory token0AfterReserve = _reserveSnapshot(matched[0]);
        ReserveSnapshot memory token1AfterReserve = _reserveSnapshot(matched[1]);
        uint256 repaidDebt1 = debt1Before - _word(afterPosition, 14);
        require(repaidDebt1 > 0, "no positive debt1 repayment occurred");
        require(
            token1BeforeReserve.accruedDebt >= token1AfterReserve.accruedDebt &&
            token1BeforeReserve.accruedDebt - token1AfterReserve.accruedDebt == repaidDebt1,
            "position debt1 repayment differs from actual reserve borrow delta"
        );
        require(
            token1AfterReserve.realCash >= token1BeforeReserve.realCash &&
            token1AfterReserve.realCash - token1BeforeReserve.realCash == repaidDebt1,
            "actual reserve token1 cash deposit differs from debt1 reduction"
        );
        require(
            token1BeforeReserve.totalLiquidity == token1AfterReserve.totalLiquidity,
            "repayment violated total reserve asset conservation"
        );
        require(
            token0AfterReserve.accruedDebt == token0BeforeReserve.accruedDebt &&
            token0AfterReserve.realCash == token0BeforeReserve.realCash &&
            token0AfterReserve.totalLiquidity == token0BeforeReserve.totalLiquidity,
            "unused token0 reserve was unexpectedly modified"
        );
        emit log_named_uint("VERIFIED_POSITION_DEBT1_REPAID", repaidDebt1);
        emit log_named_uint("VERIFIED_RESERVE1_CASH_INCREASE",
            token1AfterReserve.realCash - token1BeforeReserve.realCash);

    }
}
