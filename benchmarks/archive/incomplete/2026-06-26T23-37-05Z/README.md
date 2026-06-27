# Incomplete benchmark run - 2026-06-26T23-37-05Z

This run was interrupted by a harness failure before the benchmark could complete.
It is preserved for historical traceability only and is not a valid benchmark result.

Failure note:
- The first detector-wired Phase 1 invocation terminated before completion because the harness wrote a JSON-style boolean (`true`) instead of the Python boolean `True` while constructing the manifest entry.
- The corrected rerun completed successfully at `2026-06-26T23-39-19Z` and is the valid active artifact in `benchmarks/damn-vulnerable-defi/runs/`.
