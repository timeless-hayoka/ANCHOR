# Extra Finance vault #3 — original deployment transaction and ABI boundary

**Read-only reconstruction, 2026-11-04.** This report complements
`docs/EXTRA_HISTORICAL_LOGIC_IDENTITY_20261104.md` and the previous
gauge/oracle evidence. No transactions, storage modifications or
liquidation calls were made.

## Original creation independently located

OP Mainnet explorer attributes the creation of historical vault #3,
`0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9`, to
[transaction `0xbdd878d0e7cdf19d7a25013839ac5a9ff677b923a6a42c4c41eba2583b3d4459`](https://optimistic.etherscan.io/tx/0xbdd878d0e7cdf19d7a25013839ac5a9ff677b923a6a42c4c41eba2583b3d4459),
**block 96,268,610, May 4, 2023 06:25:22 UTC**.

- Transaction sender: `0x9088b976e9542d0A27f4F9ddc7A716c7714806ea`, labeled Extra Finance Deployer.
- Transaction receiver/factory: `0x155620A2E6A9392c754B73296d9655061525729B`.
- Explorer internal transaction: **CREATE2**, receiver/factory → vault `0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9`.
- Recorded call selector: `0xf18efb45`. **Function signature is not independently verified** by the historical factory ABI.
- Calldata consists of a 4-byte selector followed by 14 32-byte ABI words:
  first offset 32, second length 384, then 384 bytes of payload.
- Within the dynamic payload, its first three words are
  `0x20`, `0x4200000000000000000000000000000000000042` (OP),
  and `0x7F5c764cBc14f9669B88837ca1490cCa17c31607` (USDC.e).
  The remaining uninterpreted words are preserved exactly in
  `evidence/extra_finance_vault3_creation_transaction_20230504.json`.

These are **explorer-reported creation facts**; the ABI interpretation
beyond the generic outer dynamic-bytes encoding is intentionally limited.
The original EVM CREATE2 salt/creation initcode, initialization effects,
and deployed version have **not** been authenticated by a full trace.

## Versioning caveat

The pinned upstream reference `ExtraFi/extra-contracts` at
`a66e925d78ee5c990eb2bafa5009cebcbeafe42d` includes a
`VaultFactory.newVault(bytes)` entrypoint and a
`VaultDeployerSelector.deploy` that decodes its own `params`
using `abi.decode(params, (uint16, bytes))`.

That version-tagged wrapper **cannot be applied directly** to the
384-byte dynamic calldata payload observed in the 2023 creation transaction:
although the first payload word is `32`, the next word is the OP
token address, far outside the valid bytes-offset range. This proves an
**encoding mismatch with that specific reference wrapper**, *not* the
historical function signature or actual deployment version.

The factory itself is currently marked **unverified** on the explorer.
It is unsafe to assume that the 2023 factory and selector had the
same implementation as the pinned later upstream source. Equally,
the 2024 historical registry containing version 1 entries does not
prove that those same entries constructed this vault on May 4, 2023.

## Remaining source-matching sequence

1. Obtain the complete `debug_traceTransaction`/equivalent provider
   record for the creation transaction. Extract parent call frames,
   CREATE2 salt/initcode hash, initialization calls, and any
   event or internal delegatecall provenance. A transaction receipt
   alone will not recover arbitrary internal call data.
2. Cross-check the vault's code at its creation block and the later
   study block 120000000; record possible runtime changes.
3. Recover the historical factory implementation or source and
   map selector `0xf18efb45` to the actual executed entrypoint.
   Use matching codehash and deployment configuration, not selector
   names alone.
4. Resolve the vault's runtime delegation to the **executed**
   position logic and oracle modules. Registry membership is only
   a candidate source of addresses.
5. Compile candidate code with exact compiler/optimizer/links,
   verify bytecode equivalence (accounting for metadata and
   immutable arguments). Preserve a fail-closed mismatch when
   equivalence cannot be established.
6. Only then reconstruct exact LP/gauge, TWAP, spot, Chainlink,
   debt interest, and liquidation health checks and evaluate real
   historical positions. Replay only if the authentic position is
   proven unhealthy **and** a valid liquidator is authorized.

**Verdict:** `ORIGINAL_CREATE_TRANSACTION=EXPLORER_IDENTIFIED`;
`FACTORY_ABI=UNKNOWN`; `CREATION_VERSION=UNKNOWN`;
`SOURCE_EQUIVALENCE=UNPROVEN`; `LIQUIDATION_ELIGIBILITY=UNKNOWN`;
`LIQUIDATION_REPLAY=NOT_ATTEMPTED`; `BOUNTY_FINDING=NONE`.

Regression checks:

```bash
python -m pytest -q tests/test_extra_vault_creation_provenance.py
```
