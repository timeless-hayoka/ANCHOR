# Extra Finance — historical deployed logic registry identity, 2026-11-04

**Evidence tier:** authentic archived onchain inventory, **not** source-equivalent
liquidation logic or proof of eligible liquidation.

The read-only Foundry run
[41837960479](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41837960479)
passed **1/1** at Optimism block **120000000**. The exact registered
addresses, code sizes and codehashes are in
`evidence/extra_finance_op_120000000_vault3_logic_identity.json`.
This evidence is anchored to vault 3:
`0x5101081495D209a80F5DBb1C5ecd76Fe137A9eE9`, runtime
`0x957d5a09afddb11ea5ecba8566e74dd9c2e2566b878e1711069526e7ecafa480`.

## Relevant addresses and fingerprints

| Historical registry key | Interpreted role from upstream AddressId | Registered address | Historical runtime keccak256 |
|---|---|---|---|
| 103 | Legacy position logic | `0x5a583Ccb69402d60BC360D691EeDb8EfdA6Fb7E5` | `0x97d81efd7badfe963d1dd10ea0423b006f360d5019c9ec773ed1740365298bed` |
| (1 << 128) + 1001 | Version 1 vault deployer | `0xa4b43b3D33f4E583194d05485c5691C0b205a75B` | `0x3c33e223582b598efbec758ca7ceb31d7fce9bb67dedbe481fbb332c7de28744` |
| (1 << 128) + 1003 | Version 1 vault position logic | `0x512C21D420a5841a3C06636D5ee194a565a07D5C` | `0xf62a4bd972dddebaa651d7a82ffcfb419e15904fc28fee8d994b84d2f252dd60` |
| (1 << 128) + 1004 | Version 1 vault rewards logic | `0x360b864a59240eEbDa0f1a9B2534Ea96ED591B53` | `0xd07c85404c20c2189861177fe6029223853be3008e9d55329afcdc66296b3b5b` |
| 107 | Chainlink adapter | `0xBEdfdA828475005Dc8E4a09Aaa34BD0b8CA807e4` | `0xa7b7421f9098808699cc33a35add9b92ddda49d89016130ef8fb6131281c9007` |

The same archive returned registered modules for keys 101, 102, 104,
105, 106 and version 1 keys 1002 and 1005. Unversioned 1001–1005
and version 2/3 equivalents in the tested range were not registered.

**Important:** A module being in AddressRegistry proves it was configured
at that historical block. It does **not** prove which module was used to
deploy vault #3 or which one the vault called to evaluate liquidation.
The optional `implementation()` getter on vault #3 was unavailable,
which neither proves nor disproves nonstandard delegation.

## Source lookup (2026-11-04)

The source/bytecode match of the vault and sampled position logic is
**NOT_PROVEN**. In current OP explorer checks, the vault itself, the
legacy key 103 logic, the version 1 key 1003 logic, and version 1
deployer were marked unverified. Sourcify v2 contract lookups
returned no matches for these addresses. This does **not** prove no
source exists elsewhere, nor that published upstream interfaces are
equivalent to the compiled deployed runtime.

Published `ExtraFi/extra-contracts` at
`a66e925d78ee5c990eb2bafa5009cebcbeafe42d` documents
`VaultDeployerSelector`, `AddressId.versionedAddressId`,
`VaultTypes`, `VeloPositionManager`, and `IVeloVault` interfaces.
The manager delegates a liquidation callback to the vault. It does
not itself expose the authoritative vault liquidation arithmetic.

## Exact next blocker: prove **dispatch and bytecode equivalence**

1. Retrieve the **original deployment** transaction for vault #3 and
   decode the requested vault version, deployer and initialization data.
   Do not assume the current registry entry is the one used at creation.
2. Inspect the *historical* vault runtime bytecode (13,930 bytes) for
   selectors, external-library links, delegatecall targets, immutables
   and deployment differences. Map the actual liquidation selector
   to the precise code path and library address as of block 120000000.
3. Find original source/compiler metadata for that code path or compile
   candidate source with matching settings and compare the onchain
   runtime byte-for-byte, identifying metadata and immutable/link
   differences. A function-name or ABI resemblance is **not** enough.
4. Only once the executed liquidation logic is source-matched,
   reconstruct its **actual** LP-share/gauge accounting, TWAP window,
   spot/stable-pair pricing, Chainlink quote/scale/freshness and
   maxPriceDiff checks, interest/debt index and liquidation predicate.
5. Evaluate the real historical position state under those rules.
   `ELIGIBLE` requires full evidence, including liquidation access.
   With an `UNKNOWN` flag or missing dependency, **do not replay**.
6. Once independently eligible, use an isolated fork for liquidation
   and independently reconcile vault/gauge LP, debt shares,
   reserves/ERC-20 custody, fees and owner/liquidator balances.
   Preserve scope gates, Trinity Watcher checks and private disclosure.

**Research verdict:** `SOURCE_EQUIVALENCE=UNKNOWN`,
`LIQUIDATION_ELIGIBILITY=UNKNOWN`, `REPLAY=NOT_ATTEMPTED`,
`BOUNTY_FINDING=NONE`.

The narrow research trigger PR used to collect this run must not be
merged into main.

### Deterministic snapshot tests

```bash
python -m pytest -q tests/test_extra_historical_logic_identity_snapshot.py
```

These tests validate saved evidence consistency; they do not substitute
for the historical fork run itself.
