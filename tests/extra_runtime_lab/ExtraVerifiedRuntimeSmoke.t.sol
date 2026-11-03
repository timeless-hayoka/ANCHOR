// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

/// @notice Isolated EVM smoke of verified deployed runtime, not a PoC.
/// @dev No RPC fork; Forge VM etches public runtime into a disposable local address.
interface Vm {
    function envBytes(string calldata name) external returns (bytes memory);
    function envAddress(string calldata name) external returns (address);
    function etch(address who, bytes calldata code) external;
}

contract ExtraVerifiedRuntimeSmokeTest {
    Vm private constant vm = Vm(
        address(uint160(uint256(keccak256("hevm cheat code"))))
    );

    function test_DeployedRuntimeReturnsImmutableRegistry() public {
        bytes memory code = vm.envBytes("EXTRA_RUNTIME");
        address expected = vm.envAddress("EXTRA_REGISTRY");
        require(code.length > 100, "runtime unexpectedly small");
        require(expected != address(0), "missing expected immutable value");

        address local = address(uint160(0xb0b0));
        vm.etch(local, code);
        (bool success, bytes memory answer) = local.staticcall(
            abi.encodeWithSignature("addressRegistry()")
        );
        require(success && answer.length == 32, "registry getter unavailable");
        address actual = abi.decode(answer, (address));
        require(actual == expected, "registry immutable differs from provider value");
    }
}
