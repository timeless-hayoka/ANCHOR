# Proof, Finder and Foundry gate validation

Base: ANCHOR `4d13b06a6f1d698aabab7bbef6bb92a45e68fae8`.
PR #26 is merged; its final Python baseline passed. The latest main Python
baseline also passed, but the benchmark verifier previously ran only in the
scheduled/manual continuous-evidence workflow. PR CI now executes it as well.

## Executed locally

- Full regression after fixing a directory-name-dependent test assertion:
  **284 passed, 1 skipped, 18 subtests passed**. The first run failed because
  the checkout was named `ANCHOR-validation`; the assertion now checks the
  actual resolved repository root rather than requiring the name `ANCHOR`.
- `python anchor_cli.py benchmark sarif known-findings`, followed by
  `python scripts/verify_sarif_benchmark.py`: all four positive/negative controls
  passed, with no false positives or false negatives.
- Focused discovery/Finder/Sentinel tests: **39 passed, 18 subtests passed**.
- Real public-metadata crawl bounded to `repo:timeless-hayoka/ANCHOR`, limit 1:
  one complete candidate, no incomplete enrichment. Selection and planning
  completed; the untouched scope template returned `NOT AUTHORIZED`, planning
  only, exit 1. This is the expected negative control, not a failed gate.
- Foundry v1.8.7 against DVD
  `1fceebd31fe097eb00d8b44ad50e5fd62a3606b0`: **12 tests passed** across six
  initial-state/solution suites (ABI Smuggling, Backdoor, Naive Receiver,
  Side Entrance, Truster and Unstoppable).

## Coverage boundaries

Fixture scope approvals are synthetic and authorize no external target. The
live Finder check retrieved only the user's public repository metadata; it did
not scan or exploit a target. SARIF labels validate benchmark behavior, not
real-world exploitability. Foundry results cover these six existing educational
lab proofs, not every DVD challenge or a production deployment.

The baseline workflow now preserves benchmark and Foundry artifacts on failure
as well as success. Consult the follow-up PR checks for hosted results on the
final revision; a local pass alone does not certify hosted CI.
