# DVD Phase 1 Scaffold Run - 2026-06-27T00-10-52Z

## Metadata
- Benchmark ID: `dvd-phase1-local`
- Executed at: `2026-06-27T00:10:52.207733+00:00`
- ANCHOR commit: `fff5e75e20be169513c7115a52ca6e7da059b74d`
- ANCHOR branch: `main`
- DVD commit: `1fceebd31fe097eb00d8b44ad50e5fd62a3606b0`
- DVD branch: `trinity-dvdf-unstoppable-validation`

## Environment
- OS: `Linux-6.17.0-35-generic-x86_64-with-glibc2.39`
- Forge: `forge Version: 1.7.1
Commit SHA: 4072e48705af9d93e3c0f6e29e93b5e9a40caed8
Build Timestamp: 2026-05-08T07:50:55.527285345Z (1778226655)
Build Profile: dist`
- Per-challenge timeout: `90s`

## Detector provenance
- Slither: `available` · 0.11.5`
- Mythril: `unavailable` · ModuleNotFoundError: No module named 'pkg_resources'`

## Results summary
- passed: `1`
- failed: `1`
- skipped: `0`
- timed out: `1`
- aligned: `1`
- environment sensitive: `1`
- investigate: `1`
- diverged: `0`
- detector signals: `3`
- raw detector findings: `566`
- target-relevant detector findings: `304`
- medium/high target-relevant findings: `22`

## Per-challenge comparison
- `shards` -> observed `PASSED` / expected `pass` / comparison `aligned`
  - anchor output: detection `signals_present`, reproduction `reproduced_real`, council `not_reviewed`
  - detector stage: slither `completed` raw `288` / target-relevant `26` / medium-high target-relevant `16`; top target checks: unchecked-transfer, naming-convention, reentrancy-no-eth
  - path: `test/shards/Shards.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T00-10-52Z/shards.log`
- `wallet-mining` -> observed `TIMED_OUT` / expected `pass_or_timeout_needs_investigation` / comparison `investigate_but_not_regression`
  - anchor output: detection `signals_present`, reproduction `repro_timed_out`, council `not_reviewed`
  - detector stage: slither `completed` raw `9` / target-relevant `9` / medium-high target-relevant `2`; top target checks: missing-zero-check, incorrect-return, unchecked-transfer
  - path: `test/wallet-mining/WalletMining.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T00-10-52Z/wallet-mining.log`
- `withdrawal` -> observed `FAILED` / expected `environment_dependent` / comparison `environment_sensitive`
  - anchor output: detection `signals_present`, reproduction `repro_failed`, council `not_reviewed`
  - detector stage: slither `completed` raw `269` / target-relevant `269` / medium-high target-relevant `4`; top target checks: unused-state, missing-zero-check, locked-ether
  - path: `test/withdrawal/Withdrawal.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T00-10-52Z/withdrawal.log`

## Limitations
- Detector-stage outputs now include provenance and scoped summaries, but detector quality is still based on one active detector on this machine.
- Mythril is currently recorded as `unavailable` and is not part of the active detector pass.
- Challenges that require RPC or external environment will be reflected directly in the logs.
- Individual challenge runs are capped at 90s to keep the benchmark reproducible.

## Next Actions
- Add comparative detector baselines beyond Slither once Mythril or an equivalent symbolic layer is healthy again.
- Expand the challenge set beyond the initial three paths once the comparison schema is stable.
