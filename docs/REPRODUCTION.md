# Independent reproduction guide

This guide is the **credibility milestone** for ANCHOR Phase C. Anyone on a clean machine should be able to clone the repo, run the benchmark spine, and compare output to published artifacts in `benchmarks/index.json`.

ANCHOR computes trends and strategy in one place (`anchor_trends.py`, `anchor_strategy.py`). The CLI, HTTP API, and dashboard **consume** those modules — they do not recompute trend math.

## What you will verify

After following this guide you can answer:

| Question | Command / artifact |
| -------- | ------------------ |
| What happened? | `./anchor benchmark latest` |
| What changed? | `./anchor benchmark compare <run_a> <run_b>` |
| What is unstable? | `./anchor benchmark trends` |
| What should we work on next? | `./anchor strategy` |

Published runs live in the manifest at `benchmarks/index.json`. Your local DVD run creates a **development** entry until you explicitly publish it.

## Prerequisites

| Tool | Required | Notes |
| ---- | -------- | ----- |
| Python 3.11+ | Yes | Used by `./anchor` wrapper |
| Git | Yes | Clone ANCHOR and Damn Vulnerable DeFi |
| Foundry (`forge`, `cast`) | Yes for DVD Phase 1 | [getfoundry.sh](https://getfoundry.sh) |
| Slither | Optional | Improves detector signal; benchmark still runs without it |

Minimum disk: ~2 GB for ANCHOR + DVD checkout + Foundry artifacts.

## Quick path (five commands)

```bash
git clone https://github.com/timeless-hayoka/ANCHOR.git
cd ANCHOR

./anchor env init
.venv/bin/pip install -r requirements.txt

git clone https://github.com/theredguild/damn-vulnerable-defi.git ../damn-vulnerable-defi
export ANCHOR_DVD_ROOT="$(cd ../damn-vulnerable-defi && pwd)"

./anchor benchmark dvd phase1
./anchor benchmark latest
./anchor benchmark trends
./anchor strategy
```

Expected: Phase 1 completes with a run directory under `benchmarks/damn-vulnerable-defi/runs/`, a manifest entry, human-readable `latest` summary, trend lines (reproduction rate, top improved, most unstable), and a strategy recommendation when open challenges exist.

## Step-by-step

### 1. Clone ANCHOR

```bash
git clone https://github.com/timeless-hayoka/ANCHOR.git
cd ANCHOR
```

### 2. Python environment

```bash
./anchor env init
.venv/bin/pip install -r requirements.txt
```

The `./anchor` script prefers `.venv/bin/python` when present.

Run the test suite to confirm the install:

```bash
.venv/bin/python -m pytest tests/ -q
```

### 3. Install Foundry

If `forge` is not on your `PATH`:

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
forge --version
```

### 4. Clone Damn Vulnerable DeFi (authorized local target)

```bash
git clone https://github.com/theredguild/damn-vulnerable-defi.git
export ANCHOR_DVD_ROOT="$(pwd)/../damn-vulnerable-defi"
```

Default if unset: `/home/crexs/damn-vulnerable-defi` (override on any machine).

Install DVD dependencies per upstream README (`forge install`, etc.) before running the benchmark.

### 5. Run DVD Phase 1 benchmark

```bash
./anchor benchmark dvd phase1
```

This executes `benchmarks/damn-vulnerable-defi/run_phase1_benchmark.py`, writes artifacts under `benchmarks/damn-vulnerable-defi/runs/<timestamp>/`, and appends a manifest entry.

Useful environment overrides:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `ANCHOR_DVD_ROOT` | see above | Path to DVD checkout |
| `ANCHOR_BENCHMARK_LABEL` | `dvd-phase1-local` | Label stored in the run record |
| `ANCHOR_BENCHMARK_TIMEOUT_SEC` | `90` | Per-challenge timeout |

### 6. Inspect results

```bash
./anchor benchmark history
./anchor benchmark latest
./anchor benchmark trends
./anchor strategy
```

JSON for automation:

```bash
./anchor benchmark trends --json
./anchor strategy --json
```

### 7. Compare to published artifacts

Open `benchmarks/index.json` and find entries with `"publication_tier": "published"`. Compare your run's `benchmark.json` under the run directory to a published run's artifact.

Compare two manifest run ids:

```bash
./anchor benchmark compare <run_id_a> <run_id_b>
```

Regression check (optional):

```bash
./anchor benchmark regression
```

## HTTP API (optional)

Start the ANCHOR server:

```bash
.venv/bin/python anchor_server.py
```

Endpoints (same canonical math as CLI):

| Endpoint | Payload field |
| -------- | ------------- |
| `GET /api/anchor/snapshot` | `benchmark_trends`, `benchmark_strategy` |
| `GET /api/anchor/benchmark/trends` | trend object |
| `GET /api/anchor/strategy` | strategy object |

Dashboard at `/anchor` renders snapshot fields only — no client-side trend calculations.

## Troubleshooting

**`DVD root not found`**

Set `ANCHOR_DVD_ROOT` to your local Damn Vulnerable DeFi clone.

**Forge compile failures in DVD**

Run `forge build` inside the DVD repo and follow upstream setup.

**Empty trends (`published_count: 0`)**

Trends analyze **published** manifest entries. Local runs are `development` until promoted:

```bash
./anchor benchmark publish <run_id>
```

**Timeouts on brute-force challenges**

Increase `ANCHOR_BENCHMARK_TIMEOUT_SEC` or accept `TIMED_OUT` as an environment-sensitive outcome (recorded in the artifact).

## Architecture reference

```text
benchmarks/index.json  →  manifest (source list)
anchor_trends.py       →  single source of truth for trend math
anchor_strategy.py     →  consumer (never recomputes trends)
CLI / HTTP / dashboard →  renderers
```

Phase D corpus expansion (Ethernaut, DeFiHackLabs, ScaBench) waits until this reproduction path is verified on an independent machine.

## Reporting issues

If your output diverges from published artifacts after following this guide, open an issue with:

- ANCHOR commit hash
- DVD commit hash
- `forge --version`
- Manifest run id
- Relevant section of `benchmark.json`
