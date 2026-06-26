# Phase 1 Reproducible Benchmark Scaffold

This document begins the transition from the Phase 0 benchmark artifact to a true Phase 1 reproducible benchmark.

## Goal

Produce repeatable benchmark runs from a clean local checkout of Damn Vulnerable DeFi and record:

- benchmark metadata
- environment details
- exact commands used
- per-challenge outcomes
- logs and limitations

## Current scope

The initial scaffold targets the three challenge paths already exposed by the ANCHOR demo artifact:

- `test/shards/Shards.t.sol`
- `test/wallet-mining/WalletMining.t.sol`
- `test/withdrawal/Withdrawal.t.sol`

## Run command

```bash
python3 benchmarks/damn-vulnerable-defi/run_phase1_benchmark.py
```

Optional overrides:

```bash
ANCHOR_DVD_ROOT=/path/to/damn-vulnerable-defi \
ANCHOR_BENCHMARK_LABEL=dvd-phase1-local \
python3 benchmarks/damn-vulnerable-defi/run_phase1_benchmark.py
```

## What the scaffold records

- ANCHOR git commit and branch
- DVD git commit and branch
- Forge version
- operating system
- execution timestamp
- per-challenge command, duration, return code, status, and log path

## Next step to reach a stronger Phase 1

Add challenge expectation labels and ANCHOR detector outputs so the benchmark can publish automated detection metrics instead of only execution outcomes.
