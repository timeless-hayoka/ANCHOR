# DVD Phase 1 Scaffold Run - 2026-06-26T23-47-11Z

## Metadata
- Benchmark ID: `dvd-phase1-local`
- Executed at: `2026-06-26T23:47:11.352547+00:00`
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
- Slither: `/home/crexs/.local/bin/slither`
- Mythril: `unavailable` - ModuleNotFoundError: No module named 'pkg_resources'

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

## Per-challenge comparison
- `shards` -> observed `PASSED` / expected `pass` / comparison `aligned`
  - anchor output: detection `signals_present`, reproduction `reproduced_real`, council `not_reviewed`
  - detector stage: slither `completed` with `288` finding(s); top checks: events-maths, locked-ether, missing-zero-check
  - path: `test/shards/Shards.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T23-47-11Z/shards.log`
- `wallet-mining` -> observed `TIMED_OUT` / expected `pass_or_timeout_needs_investigation` / comparison `investigate_but_not_regression`
  - anchor output: detection `signals_present`, reproduction `repro_timed_out`, council `not_reviewed`
  - detector stage: slither `completed` with `9` finding(s); top checks: assembly, constable-states, incorrect-return
  - path: `test/wallet-mining/WalletMining.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T23-47-11Z/wallet-mining.log`
- `withdrawal` -> observed `FAILED` / expected `environment_dependent` / comparison `environment_sensitive`
  - anchor output: detection `signals_present`, reproduction `repro_failed`, council `not_reviewed`
  - detector stage: slither `completed` with `269` finding(s); top checks: assembly, immutable-states, locked-ether
  - path: `test/withdrawal/Withdrawal.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T23-47-11Z/withdrawal.log`

## Limitations
- Detector-stage outputs are now wired through Slither, but the scaffold does not yet normalize detector quality or compare against another tool baseline.
- Mythril is currently recorded as `unavailable` on this machine and is not part of the active detector pass.
- Challenges that require RPC or external environment will be reflected directly in the logs.
- Individual challenge runs are capped at 90s to keep the benchmark reproducible.

## Next Actions
- Add comparative detector baselines beyond Slither once Mythril or an equivalent symbolic layer is healthy again.
- Expand the challenge set beyond the initial three paths once the comparison schema is stable.
