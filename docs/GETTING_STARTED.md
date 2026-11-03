# Your first local ANCHOR run

Start with the bundled SARIF corpus. You will check how ANCHOR ingests, deduplicates, filters, and classifies tool signals against four labeled examples. This is a pipeline regression check, not an exploit reproduction or an audit of a real contract.

Prefer a browser tour first? [Open the static demo](https://timeless-hayoka.github.io/ANCHOR/). The website does not connect to your local engine.

## What you need

- Git and Python 3.11 or newer, including `venv` and `pip`.
- A Linux terminal, macOS terminal, or a Linux terminal in Windows WSL.
- Internet access to clone the repository and install dependencies. The corpus run itself uses bundled inputs.

This first run needs no wallet, RPC endpoint, API key, Foundry, Slither, companion repository, or external target. Use a dedicated virtual environment. Do not paste secrets into the browser demo.

## 1. Install in a fresh checkout

```bash
git clone https://github.com/timeless-hayoka/ANCHOR.git
cd ANCHOR
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Check that the printed Python version is 3.11 or newer. If your system uses `python3.11` or `python3.12`, substitute that executable when creating the environment. On Linux, a missing `venv` module means you need your distribution's Python venv package before proceeding.

The commands use the virtual environment directly, so activating it is optional.

## 2. Run the local corpus

```bash
.venv/bin/python anchor_cli.py benchmark sarif known-findings
.venv/bin/python scripts/verify_sarif_benchmark.py
```

The first command prints a timestamped run ID and a report path. The second verifies the newest generated `benchmark.json` by filesystem modification time, recalculates classifications, checks summary counts, and requires both positive and negative controls.

Expected verifier output on the current bundled corpus:

```text
PASS: 4 labeled cases; no FP/FN; positive and negative controls verified
```

Expected counts: **3 true positives, 1 true negative, 0 false positives, 0 false negatives**. These describe visibility of bundled tool signals. They do not mean three exploitable vulnerabilities were found or reproduced.

If the verifier exits nonzero, stop and inspect the failure. Do not publish or present a failed run as verified.

## 3. Inspect the evidence

Use the exact run directory printed by the command, under:

```text
benchmarks/sarif-known-findings/runs/<timestamp>/
```

| File | What to inspect |
| --- | --- |
| `REPORT.md` | Per-case result, limitations, and explanations |
| `benchmark.json` | `results` and `results_summary`: expected versus actual visibility and TP/FP/FN/TN classifications |
| `metrics.json` | Counts, metrics, and `source_commit` identifying the code you ran |
| Per-case `.db` files | Local pipeline storage; not needed to read the summary |

Compare the original inputs in `benchmarks/sarif-known-findings/inputs/corpus.json` with each result. The verifier reads generated outputs; it does not independently execute a smart-contract exploit.

## 4. Understand what changed locally

The runner creates the timestamped run directory, updates `benchmarks/sarif-known-findings/REPORT.md`, and appends a **development** entry to `benchmarks/index.json`. Generated run directories are ignored by Git; the manifest and summary can appear modified in `git status`.

A local successful run is not automatically a published benchmark. Preserve the artifacts you need before cleaning up. [Publication and evidence rules](BENCHMARK_PUBLICATION_REVIEW.md) explain the missing historical records and the requirements for future publication.

## Troubleshooting

| Symptom | Next action |
| --- | --- |
| `python3: command not found` or version below 3.11 | Install a supported Python version, then recreate the environment |
| `No module named venv` / `ensurepip` unavailable | Install your OS's Python venv support and retry environment creation |
| `ModuleNotFoundError` | Run the requirements install with `.venv/bin/python`, then use that same interpreter |
| No generated benchmark found | Confirm the first command completed successfully from the repository root |
| FP/FN or inconsistent counts | Inspect the printed run's `REPORT.md` and `benchmark.json`; keep the failed output |
| “No API key” while using another workflow | Return to the exact bundled-corpus commands above; they need no model credentials |

## Next: actual contract reproduction

Read the [proof gate](PROOF_GATE.md) and [methodology](METHODOLOGY.md). Then follow the [independent reproduction guide](REPRODUCTION.md) for the authorized local Damn Vulnerable DeFi lab, which requires additional tooling. Confirm scope and prerequisites before testing any external target.

## Verification of this guide

On 2026-11-03, the install and corpus commands above were executed in a fresh detached checkout of commit `62aa7294235d6b824c7c008e02d553011b6953e4` with a new virtual environment and installed repository requirements. All four corpus cases passed (3 TP, 1 TN); the verifier passed. Run `sarif-known-findings-2026-11-03T10-43-45Z` was a new development run, not a recovery of the missing June artifacts. Results can change when the corpus or dependencies change.
