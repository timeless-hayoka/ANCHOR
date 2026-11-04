# Extra Finance — historical active position and successful local-fork close

**Evidence date:** 2026-11-04 UTC. **Chain:** Optimism Mainnet (10). **Pinned block:** `120000000`. **LendingPool:** `0xbb505c54d71e9e599cb8435b4f0ceec05fc71cbd`.

## Candidate discovery (verified historical storage)

[Historical discovery GitHub Actions run 41785477648](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41785477648) completed both block-pinned scans successfully, before additional concurrent scans caused public-RPC throttling.

- **At block 120000000:** discovered 3 real vault contracts, 41 recorded position entries among bounded IDs, and **one active position with debt and liquidity**.
- **At block 145000000:** the same bounded sampling reported **zero active positions**. This does not prove there were no active positions outside the scanned IDs/vaults.
- The independently located Vault Position Manager was `0xf9cFB8a62f50e10AdDE5Aa888B44cF01C5957055` at block 120000000. The registry/factory addresses were read from the deployed LendingPool contract rather than assumed.
- The selected candidate was **vault 3 / position 16**, whose recorded manager was `0x24e32bB964721dFAC9DEE9E9FF71Ac476652E8eF`. The actual `getVaultPosition(3,16)` return was 19 ABI words long, with `isActive=true`, nonzero liquidity and debt-1.
- The position's exact ABI-return bytes were fingerprinted using **Keccak-256** (not SHA-256): `0xfdbf41f35b21cdd886cb461a53f4ed745332d99bb3f9deecc46585d1dac0df53`.

## Strict positive control: actual manager's 10% partial close (fork only)

[Final passing Foundry fork run 41786252785](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41786252785) executed `test_HistoricalRecordedManagerCanClosePartOfRealActivePosition` at pinned Optimism block **120000000** against the actual deployed Vault Position Manager and onchain storage. **1 test passed, 0 failed**.

The test uses `vm.prank(recordedManager)` **inside a disposable Foundry fork**; no account key, impersonation on the public network, live broadcast or production storage override was used. It called `closeVaultPositionPartially` with **10%** (1000 basis points), receiveType=2, receiver=recorded manager, zero slippage minima and a deadline relative to the historical block. The call **succeeded** and the real position and vault-state records both changed.

| Actual field | Before | After |
|---|---:|---:|
| Position active flag | true | true |
| Position owner/manager | same historical manager | unchanged |
| Recorded liquidity | 40055866659254 | 36050279993330 |
| Recorded debt-0 share/value | 0 | 0 |
| Recorded debt-1 share/value | 40894860 | 36805375 |
| Position ABI Keccak-256 | `0xfdbf41f35b21cdd886cb461a53f4ed745332d99bb3f9deecc46585d1dac0df53` | `0x1036ba60e63b8d79850f26435338c8a3e4a5065655e6ceb698ea0b062810eeee` |
| Full vault state Keccak-256 | `0xead1699058a2b7572dfafc5e67e947a4d1d15c222f26bf37bda28c208b5c214d` | `0x9716773310ce1821942f00c4348a0a1627c5771e30aae53ea0dad031d235e161` |

The passing assertions verify: existing manager unchanged, active flag remains true, principals did not increase, liquidity decreased, debt-0 did not increase and debt-1 **decreased**, actual position ABI bytes changed, and the entire vault-state ABI changed. Amounts are **raw contract units**; `debt1` here is the position getter's value, not an independently reconstructed USD valuation.

## Independent ERC-20 cash and LendingPool debt reconciliation (2026-11-04)

[Confirmed pinned historical close run 41791446538](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41791446538) **passed 1/1 Foundry tests** at Optimism block `120000000`, with new strict assertions tying the partial close to independently read underlying ERC-20 custody and actual reserve debt, in addition to the existing position/vault-state checks.

The real vault's `token0` is `0x4200000000000000000000000000000000000042` (matched to reserve #4), and `token1` is `0x7F5c764cBc14f9669B88837ca1490cCa17c31607` (matched to reserve #2). The test independently calculates reserve cash as `IERC20(underlying).balanceOf(eToken)`, and asserts `totalLiquidity == cash + accruedDebt` both before **and** after the successful close. The deployed vault token balances were also measured before/after; token0 remained 0 and token1 remained 22,518 raw units in this scenario.

| Independently measured raw amount | Before close | After close | Delta |
|---|---:|---:|---:|
| Position debt1 value | 40,894,860 | 36,805,375 | **−4,089,485** |
| Reserve #2 accrued borrowing | 4,727,549,666,438 | 4,727,545,576,953 | **−4,089,485** |
| Actual reserve #2 eToken custody cash | 991,534,170,233 | 991,538,259,718 | **+4,089,485** |
| Reserve #2 total liquidity | 5,719,083,836,671 | 5,719,083,836,671 | **unchanged** |
| Reserve #4 cash | 192,627,114,451,947,060,026,038 | 192,627,114,451,947,060,026,038 | unchanged |
| Reserve #4 accrued borrowing | 119,915,476,017,678,300,196,063 | 119,915,476,017,678,300,196,063 | unchanged |

The test now *fails* if position debt1 reduction differs by even one base unit from reserve #2's borrowing reduction, if reserve #2 cash increase differs from the repayment, if either reserve violates independent cash-plus-borrow accounting, or if the unused token0 reserve changes. The expected manager's 10% close must still succeed and position/vault state hashes must change.

**Verdict:** This is an independently reconciled **expected, successful partial close**, not a violation. The selected owner was simulated via Foundry `vm.prank` only inside the local fork, and all contract state was taken from the recorded historical snapshot. It does not establish liquidation eligibility, collateral health, a malicious caller's profit, or a reportable bug. Future liquidation tests require a separately verified unhealthy position; do not modify oracles/storage to manufacture one.

## Limitations and disclosure status

This provides **one real historical authorized partial-close state transition**. It is not an active liquidation-eligibility determination, liquidation test, generalized collateral-health proof, or evidence of an exploit. The deployed manager's dependency graph can include AMM state, oracle values, lending and token contracts beyond those separately asserted. Tests did not independently reconstruct every reserve token-flow delta or liquidation health ratio. No Trinity finding, CVE or bounty report is justified by this normal transition.

A subsequent concurrent historical discovery run [41785907112](https://github.com/timeless-hayoka/ANCHOR/actions/runs/41785907112) had its block-145000000 matrix job fail due **HTTP 429** from public Optimism RPC, while the strict 120000000 positive-close job passed. We therefore run wide discovery only on manual workflow dispatch, serially; the ordinary PR CI executes the focused 120000000 positive-control replay. Do not attribute public RPC throttling to the protocol.

**Research outcome: VALIDATED EXPECTED POSITIVE TRANSITION, NO NOVEL VULNERABILITY.**

Next gates: reconstruct live reserve token movements and collateral-health bounds using source-matched arithmetic; independently assess eligibility before simulating a liquidation on a *separate* pinned eligible position. Never send live transactions or force a liquidation by overriding collateral/oracle storage merely to get a green badge.
