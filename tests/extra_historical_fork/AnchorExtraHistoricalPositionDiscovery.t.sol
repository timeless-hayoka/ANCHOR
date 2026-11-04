// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

/// @notice READ-ONLY historical position discovery against a pinned Optimism
/// archive fork. Active means isActive=true in actual manager storage; this
/// test does NOT establish liquidatability or permission to close a position.
interface IAnchorHistoryRegistry {
    function getAddress(uint256 id) external view returns (address);
}
interface IAnchorHistoryFactory {
    function vaults(uint256 id) external view returns (address);
}
interface IAnchorHistoryPool {
    function addressRegistry() external view returns (address);
}
interface IAnchorHistoryPositionManager {
    // ABI tuple includes all VeloPositionValue fields from pinned upstream
    // verified type; the staticcall below reads only the first two words,
    // and logs the entire ABI response hash for repeatable provenance.
    function getVaultPosition(uint256 vaultId, uint256 positionId)
        external view returns (bytes memory);
}
contract AnchorExtraHistoricalPositionDiscoveryTest {
    event log_named_uint(string label, uint256 value);
    event log_named_address(string label, address value);
    event log_named_bytes32(string label, bytes32 value);

    address constant LENDING_POOL = 0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD;
    uint256 constant CHAIN_ID = 10;

    function test_HistoricalActivePositionDiscovery() public {
        require(block.chainid == CHAIN_ID, "not Optimism");
        emit log_named_uint("historical_snapshot_block", block.number);
        if (LENDING_POOL.code.length == 0) {
            emit log_named_uint("deployment_missing_at_block", 1);
            return;
        }
        address registry = IAnchorHistoryPool(LENDING_POOL).addressRegistry();
        require(registry.code.length > 0, "historical registry unavailable");
        address factory = IAnchorHistoryRegistry(registry).getAddress(10);
        address manager = IAnchorHistoryRegistry(registry).getAddress(7);
        if (factory.code.length == 0 || manager.code.length == 0) {
            emit log_named_uint("vault_dependencies_missing_at_block", 1);
            return;
        }
        emit log_named_address("historical_position_manager", manager);
        emit log_named_address("historical_vault_factory", factory);

        uint256 foundVaults;
        uint256 recordedPositions;
        uint256 activePositions;
        uint256 positiveDebtPositions;
        uint256 nonzeroLiquidityPositions;
        uint256[14] memory positionIds = [
            uint256(1), 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 32, 64
        ];
        for (uint256 vaultId = 1; vaultId <= 3; ++vaultId) {
            address vault = IAnchorHistoryFactory(factory).vaults(vaultId);
            if (vault.code.length == 0) continue;
            ++foundVaults;
            emit log_named_uint("sampled_vault_id", vaultId);
            for (uint256 j = 0; j < positionIds.length; ++j) {
                uint256 positionId = positionIds[j];
                // Only calldata corresponding to the verified public getter.
                (bool ok, bytes memory raw) = manager.staticcall(
                    abi.encodeWithSignature(
                        "getVaultPosition(uint256,uint256)", vaultId, positionId
                    )
                );
                // VeloPositionValue contains 19 ABI words (all static types).
                // 0:manager, 1:isActive, 2:enableRangeStop, 3:openedAt,
                // 4:current, 5/6:invest principals, 7:LP principal,
                // 8/9:left tokens, 10/11:in-liquidity, 12:liquidity,
                // 13/14:debt0/debt1, rest borrowing indices/range limits.
                if (!ok || raw.length < 19 * 32) continue;
                address user;
                uint256 activeWord;
                uint256 principal0;
                uint256 principal1;
                uint256 liquidity;
                uint256 debt0;
                uint256 debt1;
                assembly {
                    user := mload(add(raw, 32))
                    activeWord := mload(add(raw, 64))
                    principal0 := mload(add(raw, 192))
                    principal1 := mload(add(raw, 224))
                    liquidity := mload(add(raw, 416))
                    debt0 := mload(add(raw, 448))
                    debt1 := mload(add(raw, 480))
                }
                if (user == address(0) || activeWord > 1) continue;
                ++recordedPositions;
                if (activeWord != 1) continue;
                ++activePositions;
                if (debt0 > 0 || debt1 > 0) ++positiveDebtPositions;
                if (liquidity > 0) ++nonzeroLiquidityPositions;
                emit log_named_uint("ACTIVE_VAULT_ID", vaultId);
                emit log_named_uint("ACTIVE_POSITION_ID", positionId);
                emit log_named_address("ACTIVE_MANAGER", user);
                emit log_named_uint("ACTIVE_PRINCIPAL0", principal0);
                emit log_named_uint("ACTIVE_PRINCIPAL1", principal1);
                emit log_named_uint("ACTIVE_LIQUIDITY", liquidity);
                emit log_named_uint("ACTIVE_DEBT0", debt0);
                emit log_named_uint("ACTIVE_DEBT1", debt1);
                emit log_named_bytes32("ACTIVE_POSITION_ABI_HASH", keccak256(raw));
            }
        }
        require(foundVaults > 0, "no actual vaults in this historical block");
        emit log_named_uint("sampled_vault_count", foundVaults);
        emit log_named_uint("sampled_existing_positions", recordedPositions);
        emit log_named_uint("sampled_active_positions", activePositions);
        emit log_named_uint("sampled_active_with_debt", positiveDebtPositions);
        emit log_named_uint("sampled_active_with_liquidity", nonzeroLiquidityPositions);
        // An empty/closed sample is a *discovery blocker*, not a
        // false-positive security flaw or a liquidation success.
    }
}
