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
./anchor benchmark dvd phase1
```

Optional overrides:

```bash
ANCHOR_DVD_ROOT=/path/to/damn-vulnerable-defi \
ANCHOR_BENCHMARK_LABEL=dvd-phase1-local \
./anchor benchmark dvd phase1
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

## Comparison schema

The scaffold now reads `challenge_expectations.json` and records, per challenge:

- expected ground truth
- expected Phase 1 outcome
- structured ANCHOR output fields
- comparison state between expectation and observation

That gives future runs a stable history format instead of one-off prose.


## Benchmark history

```bash
anchor benchmark history --limit 5
```

This prints the latest published benchmark runs with pass/fail/timeout counts, detector signal count, and scoped medium/high target-relevant detector findings.
