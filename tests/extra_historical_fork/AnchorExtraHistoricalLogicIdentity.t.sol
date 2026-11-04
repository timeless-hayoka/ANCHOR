// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;

/// @notice Archive-only inventory of registered vault logic implementations.
/// Does not execute liquidation, write storage, or infer source equivalence.
interface IAnchorLogicPool {
    function addressRegistry() external view returns (address);
}
interface IAnchorLogicRegistry {
    function getAddress(uint256 key) external view returns (address);
}
interface IAnchorLogicFactory {
    function vaults(uint256 id) external view returns (address);
}

contract AnchorExtraHistoricalLogicIdentityTest {
    event log_named_uint(string name, uint256 value);
    event log_named_address(string name, address value);
    event log_named_bytes32(string name, bytes32 value);

    address constant POOL = 0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD;
    address constant EXPECTED_VAULT = 0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9;
    bytes32 constant EXPECTED_VAULT_CODEHASH =
        0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480;

    function _inspect(address registry, uint256 key) internal {
        // Unknown or unregistered ID is informative; never a positive match.
        (bool ok, bytes memory response) = registry.staticcall(
            abi.encodeWithSelector(IAnchorLogicRegistry.getAddress.selector, key)
        );
        if (!ok || response.length != 32) {
            emit log_named_uint("REGISTRY_LOOKUP_UNAVAILABLE_ID", key);
            return;
        }
        address implementation = abi.decode(response, (address));
        if (implementation == address(0)) {
            emit log_named_uint("REGISTRY_UNSET_ID", key);
            return;
        }
        emit log_named_uint("REGISTERED_ID", key);
        emit log_named_address("REGISTERED_ADDRESS", implementation);
        emit log_named_uint("REGISTERED_CODE_SIZE", implementation.code.length);
        if (implementation.code.length > 0) {
            emit log_named_bytes32("REGISTERED_CODE_HASH", implementation.codehash);
        }
    }

    function test_ArchivedVaultLogicRegistryIdentities() public {
        require(block.chainid == 10 && block.number == 120000000,
            "not archived OP block");
        require(POOL.code.length > 0, "lending pool missing");
        address registry = IAnchorLogicPool(POOL).addressRegistry();
        require(registry.code.length > 0, "registry missing");
        emit log_named_address("REGISTRY", registry);
        emit log_named_bytes32("REGISTRY_CODE_HASH", registry.codehash);

        address factory = IAnchorLogicRegistry(registry).getAddress(10);
        require(factory.code.length > 0, "factory missing");
        address vault = IAnchorLogicFactory(factory).vaults(3);
        require(vault == EXPECTED_VAULT, "vault identity drift");
        require(vault.codehash == EXPECTED_VAULT_CODEHASH,
            "vault historical runtime changed");
        emit log_named_address("VAULT", vault);
        emit log_named_uint("VAULT_CODE_SIZE", vault.code.length);
        emit log_named_bytes32("VAULT_CODE_HASH", vault.codehash);

        // IDs 101..107 are the published vault logic/selector/oracle families.
        for (uint256 id = 101; id <= 107; ++id) {
            _inspect(registry, id);
        }
        // Vault deployer and logic 1001..1005 may be registered
        // unversioned or under the documented 128-bit version prefix.
        for (uint256 id = 1001; id <= 1005; ++id) {
            _inspect(registry, id);
            for (uint256 version = 1; version <= 3; ++version) {
                _inspect(registry, (version << 128) | id);
            }
        }
        // These optional standard proxy getters are only source clues:
        // a revert or zero does NOT prove that this is not a proxy.
        (bool implementationOk, bytes memory rawImplementation) =
            vault.staticcall(abi.encodeWithSignature("implementation()"));
        if (implementationOk && rawImplementation.length == 32) {
            address candidate = abi.decode(rawImplementation, (address));
            emit log_named_address("OPTIONAL_PROXY_IMPLEMENTATION", candidate);
            if (candidate.code.length > 0) {
                emit log_named_bytes32("OPTIONAL_PROXY_IMPLEMENTATION_HASH",
                    candidate.codehash);
            }
        } else {
            emit log_named_uint("PROXY_GETTER_UNAVAILABLE", 1);
        }
        emit log_named_uint("EXACT_DEPLOYED_SOURCE_UNVERIFIED", 1);
        emit log_named_uint("LIQUIDATION_ELIGIBILITY_UNKNOWN", 1);
    }
}
