// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

/// @notice Historical read-only inventory of the concrete vault and AMM
/// dependencies. DOES NOT assert liquidation eligibility or oracle accuracy.
/// @dev All reads execute in a disposable fork at Optimism block 120000000.
interface IAnchorHistoricPoolRegistry {
    function addressRegistry() external view returns (address);
}
interface IAnchorHistoricRegistry {
    function getAddress(uint256 key) external view returns (address);
}
interface IAnchorHistoricVaultFactory {
    function vaults(uint256 id) external view returns (address);
}

contract AnchorExtraHistoricalOracleProvenanceTest {
    event log_named_uint(string name, uint256 value);
    event log_named_address(string name, address value);
    event log_named_bytes32(string name, bytes32 value);

    address internal constant LENDING_POOL =
        0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD;
    uint256 internal constant TARGET_BLOCK = 120000000;
    uint256 internal constant VAULT_ID = 3;
    uint256 internal constant POSITION_ID = 16;

    function _word(bytes memory payload, uint256 index)
        internal pure returns (uint256 result)
    {
        require(payload.length >= (index + 1) * 32, "missing ABI word");
        assembly {
            result := mload(add(add(payload, 32), mul(index, 32)))
        }
    }

    function _readUint(address target, bytes memory callData, string memory label)
        internal returns (bool ok, uint256 value)
    {
        bytes memory data;
        (ok, data) = target.staticcall(callData);
        if (!ok || data.length != 32) {
            emit log_named_uint(string(abi.encodePacked(label, "_UNAVAILABLE")), 1);
            return (false, 0);
        }
        value = _word(data, 0);
        emit log_named_uint(label, value);
    }

    function test_ArchivedVaultThreeDependenciesAndLPInputs() public {
        require(block.chainid == 10 && block.number == TARGET_BLOCK,
            "not pinned Optimism archive block");
        address registry = IAnchorHistoricPoolRegistry(LENDING_POOL).addressRegistry();
        require(registry.code.length > 0, "missing original registry");
        address manager = IAnchorHistoricRegistry(registry).getAddress(7);
        address factory = IAnchorHistoricRegistry(registry).getAddress(10);
        require(manager.code.length > 0 && factory.code.length > 0,
            "missing deployed dependencies");
        address vault = IAnchorHistoricVaultFactory(factory).vaults(VAULT_ID);
        require(vault.code.length > 0, "missing historic vault");

        emit log_named_uint("HISTORIC_BLOCK", block.number);
        emit log_named_address("HISTORIC_MANAGER", manager);
        emit log_named_bytes32("MANAGER_RUNTIME_CODEHASH", manager.codehash);
        emit log_named_address("HISTORIC_VAULT", vault);
        emit log_named_bytes32("VAULT_RUNTIME_CODEHASH", vault.codehash);

        (bool vaultOk, bytes memory vaultRaw) = vault.staticcall(
            abi.encodeWithSignature("getVaultState()"));
        require(vaultOk && vaultRaw.length >= 13 * 32
            && vaultRaw.length % 32 == 0, "historic vault ABI unavailable");
        emit log_named_bytes32("VAULT_STATE_ABI_HASH", keccak256(vaultRaw));
        address gauge = address(uint160(_word(vaultRaw, 0)));
        address pair = address(uint160(_word(vaultRaw, 1)));
        address token0 = address(uint160(_word(vaultRaw, 2)));
        address token1 = address(uint160(_word(vaultRaw, 3)));
        require(pair.code.length > 0 && token0.code.length > 0
            && token1.code.length > 0 && token0 != token1,
            "deployed vault assets missing");
        require(_word(vaultRaw, 8) <= 1 && _word(vaultRaw, 12) > 0,
            "invalid historic liquidation config");
        emit log_named_address("VAULT_GAUGE", gauge);
        emit log_named_address("VAULT_PAIR", pair);
        emit log_named_bytes32("PAIR_RUNTIME_CODEHASH", pair.codehash);
        emit log_named_address("VAULT_TOKEN0", token0);
        emit log_named_address("VAULT_TOKEN1", token1);
        emit log_named_uint("LIQUIDATE_WITH_TWAP_RAW", _word(vaultRaw, 8));
        emit log_named_uint("MAX_PRICE_DIFF_RAW", _word(vaultRaw, 11));
        emit log_named_uint("LIQUIDATION_DEBT_RATIO_RAW", _word(vaultRaw, 12));

        // The AMM reserve data and LP supply are raw valuation operands.
        // They are NOT a source-matched price or a complete LP valuation.
        (bool reservesOk, bytes memory reservesRaw) = pair.staticcall(
            abi.encodeWithSignature("getReserves()"));
        if (reservesOk && reservesRaw.length == 96) {
            emit log_named_uint("AMM_RESERVE0_RAW", _word(reservesRaw, 0));
            emit log_named_uint("AMM_RESERVE1_RAW", _word(reservesRaw, 1));
            emit log_named_uint("AMM_LAST_RESERVE_TIMESTAMP", _word(reservesRaw, 2));
            emit log_named_bytes32("AMM_RESERVE_ABI_HASH", keccak256(reservesRaw));
        } else {
            emit log_named_uint("AMM_RESERVES_UNAVAILABLE", 1);
        }
        _readUint(pair, abi.encodeWithSignature("totalSupply()"),
            "PAIR_TOTAL_LP_SUPPLY_RAW");
        _readUint(pair, abi.encodeWithSignature("balanceOf(address)", vault),
            "VAULT_HELD_LP_BALANCE_RAW");
        _readUint(token0, abi.encodeWithSignature("decimals()"),
            "TOKEN0_DECIMALS");
        _readUint(token1, abi.encodeWithSignature("decimals()"),
            "TOKEN1_DECIMALS");

        (bool positionOk, bytes memory positionRaw) = manager.staticcall(
            abi.encodeWithSignature("getVaultPosition(uint256,uint256)",
                VAULT_ID, POSITION_ID));
        require(positionOk && positionRaw.length == 19 * 32,
            "historical position ABI unavailable");
        require(_word(positionRaw, 1) == 1, "reference position not active");
        require(_word(positionRaw, 12) > 0, "reference position has no LP");
        emit log_named_bytes32("POSITION_ABI_HASH", keccak256(positionRaw));
        emit log_named_uint("POSITION_LP_LIQUIDITY_RAW", _word(positionRaw, 12));
        emit log_named_uint("POSITION_DEBT0_RAW", _word(positionRaw, 13));
        emit log_named_uint("POSITION_DEBT1_RAW", _word(positionRaw, 14));

        // Permissionless liquidator configuration is an independent gate.
        _readUint(manager,
            abi.encodeWithSignature("permissionLessLiquidationEnabled()"),
            "PERMISSIONLESS_LIQUIDATION_RAW");

        // The historical vault implementation's precise LP accounting,
        // TWAP/spot and optional Chainlink paths are still unverified.
        emit log_named_uint("ORACLE_PREDICATE_UNVERIFIED", 1);
        emit log_named_uint("LIQUIDATION_ELIGIBILITY_UNKNOWN", 1);
    }
}
