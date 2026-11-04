# Extra Finance — factory/vault bytecode continuity vs registry evolution

**Date:** 2026-11-04. **Scope:** actual Optimism chain 10, original
vault #3 deployment **block 96,268,610** (May 4, 2023), compared with
historical research snapshot **block 120,000,000**.

Evidence:
- Authenticated public RPC runs
  [41842764827](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41842764827),
  [41843060987](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41843060987),
  and [41843514683](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41843514683).
- Archived artifact JSON and fingerprints summarized in
  `evidence/extra_finance_2023_vs_2024_factory_registry_drift.json`.
- Previously preserved raw creation calldata:
  `evidence/extra_finance_vault3_creation_transaction_20230504.json`.
- Original transaction:
  [`0xbdd878d0…3b3d4459`](https://optimistic.etherscan.io/tx/0xbdd878d0e7cdf19d7a25013839ac5a9ff677b923a6a42c4c41eba2583b3d4459).

## 1. Exact bytecode continuity VERIFIED

The RPC-provided `eth_getCode` bytes match byte-for-byte for each of
these contract addresses across both historical block heights:

| Account | Bytes | Keccak256 of runtime | Creation == study |
|---|---:|---|---|
| Historical VaultFactory `0x155620A2E6A9392c754B73296d9655061525729B` | 2,449 | `0x94e05c7a0558dfd917427e437cc1db5e8bd9e6e73b029e47552dc601837673a4` | **YES** |
| Vault #3 `0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9` | 13,930 | `0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480` | **YES** |

The exact same codehash at the reference block was previously seen by
the independent Foundry historical tests. Runtime continuity does
**not** establish source equivalence or unchanging behavior if contract
logic depends on **mutable registry addresses**.

## 2. Historical registry evolution VERIFIED

The deployed factory's `addressRegistry()` getter was successfully
read at both blocks. It returned the same registry:
`0x85603119C938750Dfb5904f8a501b64F3F3A01D2`.
The registry's own `getAddress(uint256)` returned:

| Published `AddressId` key | At deployment block 96,268,610 | At study block 120,000,000 |
|---|---|---|
| 101 — vault deployer selector | `0x2c58ece45ac754b80fd39f5e7e67a4b0e91a1525` | `0xdcf0f4a0fc44f33de35d8c80ad5d248dbf838943` |
| 103 — position logic | `0x4f4940a87d63a290d43b6550911896ff7aee354c` | `0x5a583ccb69402d60bc360d691eedb8efda6fb7e5` |
| 107 — Chainlink oracle adapter | **UNSET** | `0xbedfda828475005dc8e4a09aaa34bd0b8ca807e4` |
| `(1 << 128) + 1001` — version 1 vault deployer | **UNSET** | `0xa4b43b3d33f4e583194d05485c5691c0b205a75b` |
| `(1 << 128) + 1003` — version 1 vault position logic | **UNSET** | `0x512c21d420a5841a3c066d5ee194a565a07d5c` |

**Key conclusion:** projecting later registry entries backward to the
2023 creation transaction is objectively invalid. The immutable
factory/vault runtime may route calls using later-addressed modules,
so bytecode continuity and executable behavior are *different*
questions. Even the original key 101 address's presence in the
creation-block registry alone cannot substitute for an actual creation
`DELEGATECALL` trace, although it provides a concrete original
candidate.

## 3. Static bytecode inventory is a clue, not a trace

A PUSH-aware EVM opcode walk, which skips immediate PUSH data, found:

| Historical runtime | DELEGATECALL opcodes | CREATE2 opcodes | STATICCALL opcodes |
|---|---:|---:|---:|
| Factory | 1 | 0 | 4 |
| Vault | 7 | 0 | 10 |

The original transaction selector `0xf18efb45` occurs among the
factory's PUSH4 bytecode constants. **This corroborates selector presence,
not a confirmed function name or ABI.** The original factory executes
no direct CREATE2 *opcode* in its own deployed runtime, which is
consistent with delegation to external deployment logic; the Etherscan
transaction explorer reports internal CREATE2 creation.

No source or execution-trace equivalence follows merely from opcode
counts. Neither the original selector nor original position-logic
contract had publicly verified source in the checked explorer pages.

The public archive RPC rejected the optional
`debug_traceTransaction(..., {tracer: "callTracer"})` request with an
HTTP error. Treat this as **TRACE UNAVAILABLE**, not as evidence of
a missing delegatecall. A debug-capable archival RPC or independent
historical trace provider is needed to recover the actual runtime
delegation target and CREATE2 input.

## 4. Faster, precise next validation

1. **Prioritize the 2023 registry state**, starting from original
   selector key 101 `0x2c58...1525` and original position logic
   key 103 `0x4f49...354c`. Record their creation-block runtime
   codehashes and search for verified source under those exact hashes.
2. Obtain a historical call trace for the original transaction with
   the actual parent→delegatecall→CREATE2 frames. Correlate delegatecall
   targets against key 101 at the original block; do not assume.
3. At the **study block**, map the vault's liquidation selector and
   executed delegatecall target against that block's registry state.
   The 2023 deployer identity and 2024 liquidation execution can be
   **different codepaths**.
4. Compile exact identified implementation/library source with proper
   optimizer/metadata/links and compare against the historical
   runtime bytes.
5. Only once source-to-runtime and oracle/LP/interest math are verified,
   evaluate authentic positions. Reproduce liquidation only if
   eligibility and liquidator authorization are actually established.

**Final gates:** `CREATION_FACTORY_RUNTIME_CONTINUITY=VERIFIED`,
`VAULT_RUNTIME_CONTINUITY=VERIFIED`,
`HISTORICAL_REGISTRY_DRIFT=VERIFIED`,
`CREATION_EXECUTED_LIBRARY=UNVERIFIED`,
`SOURCE_EQUIVALENCE=UNKNOWN`,
`LIQUIDATION_ELIGIBILITY=UNKNOWN`,
`LIQUIDATION_REPLAY=NOT_ATTEMPTED`,
`BOUNTY_FINDING=NONE`.

## Reproduce

```bash
python -m pytest -q tests/test_extra_creation_rpc_provenance.py tests/test_extra_creation_registry_drift_snapshot.py

# Optional actual archive RPC; requires Foundry cast and archive history.
# This is deliberately NOT run on ordinary PRs.
python scripts/extra_creation_rpc_provenance.py \
  --rpc-url https://mainnet.optimism.io \
  --out evidence/extra_vault3_rpc_creation_readout.json
```

Only `eth_chainId`, `eth_getTransactionByHash`,
`eth_getTransactionReceipt`, `eth_getCode`, optional historical
`eth_call`, and optional `debug_traceTransaction` are used.
No transaction submission, secrets, privilege impersonation,
storage/oracle overrides or real-money operations.
