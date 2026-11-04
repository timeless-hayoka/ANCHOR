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
    }
}
