# DVD Phase 1 Scaffold Run - 2026-06-26T23-14-42Z

## Metadata
- Benchmark ID: `dvd-phase1-local`
- Executed at: `2026-06-26T23:14:42.889092+00:00`
- ANCHOR commit: `57a31b89f9b07a9e8862b37d025dd369389ee92f`
- ANCHOR branch: `main`
- DVD commit: `1fceebd31fe097eb00d8b44ad50e5fd62a3606b0`
- DVD branch: `trinity-dvdf-unstoppable-validation`

## Environment
- OS: `Linux-6.17.0-35-generic-x86_64-with-glibc2.39`
- Forge: `forge Version: 1.7.1
Commit SHA: 4072e48705af9d93e3c0f6e29e93b5e9a40caed8
Build Timestamp: 2026-05-08T07:50:55.527285345Z (1778226655)
Build Profile: dist`
- Per-challenge timeout: `45s`

## Results summary
- passed: `1`
- failed: `1`
- skipped: `0`
- timed out: `1`
- aligned: `1`
- environment sensitive: `1`
- investigate: `1`
- diverged: `0`

## Per-challenge comparison
- `shards` -> observed `PASSED` / expected `pass` / comparison `aligned`
  - anchor output: detection `not_yet_wired`, reproduction `reproduced_real`, council `not_reviewed`
  - path: `test/shards/Shards.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T23-14-42Z/shards.log`
- `wallet-mining` -> observed `TIMED_OUT` / expected `pass_or_timeout_needs_investigation` / comparison `investigate_but_not_regression`
  - anchor output: detection `not_yet_wired`, reproduction `repro_timed_out`, council `not_reviewed`
  - path: `test/wallet-mining/WalletMining.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T23-14-42Z/wallet-mining.log`
- `withdrawal` -> observed `FAILED` / expected `environment_dependent` / comparison `environment_sensitive`
  - anchor output: detection `not_yet_wired`, reproduction `repro_failed`, council `not_reviewed`
  - path: `test/withdrawal/Withdrawal.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T23-14-42Z/withdrawal.log`

## Limitations
- This scaffold now records expected labels and structured ANCHOR outputs, but detector metrics are still not wired.
- Challenges that require RPC or external environment will be reflected directly in the logs.
- Individual challenge runs are capped at 45s to keep the benchmark reproducible.

## Next Actions
- Wire detector-stage outputs into the per-challenge benchmark record.
- Expand the challenge set beyond the initial three paths once the comparison schema is stable.
