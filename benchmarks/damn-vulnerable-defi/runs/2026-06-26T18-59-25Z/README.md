# DVD Phase 1 Scaffold Run - 2026-06-26T18-59-25Z

## Metadata
- Benchmark ID: `dvd-phase1-local`
- Executed at: `2026-06-26T18:59:25.689358+00:00`
- ANCHOR commit: `8bfff40c421872a5de80d92090a609ba247f908a`
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

## Results
- `shards` -> `PASSED` in `0.286`s (rc `0`)
  - path: `test/shards/Shards.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T18-59-25Z/shards.log`
- `wallet-mining` -> `TIMED_OUT` in `45.045`s (rc `124`)
  - path: `test/wallet-mining/WalletMining.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T18-59-25Z/wallet-mining.log`
- `withdrawal` -> `FAILED` in `0.205`s (rc `1`)
  - path: `test/withdrawal/Withdrawal.t.sol`
  - log: `benchmarks/damn-vulnerable-defi/runs/2026-06-26T18-59-25Z/withdrawal.log`

## Limitations
- This scaffold records execution outcomes, not ANCHOR detector metrics yet.
- Challenges that require RPC or external environment will be reflected directly in the logs.
- Individual challenge runs are capped at 45s to keep the benchmark reproducible.

## Next Actions
- Add expected challenge labels and ANCHOR detection outputs.
- Convert the scaffold into a benchmark that publishes automated detection metrics.
