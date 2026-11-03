# Benchmark publication review — 2026-11-03

Three historical entries were labeled published but referenced evidence files that are absent from the checkout and fetched Git history. Their original run IDs, timestamps, paths, and summary counts remain in the index. Their current tier is `development`, status is `evidence_missing`, verification is false, and `publication_review` preserves the previous state. These entries are withdrawn from published views pending original evidence recovery.

This does not prove the historical results were wrong. It means the repository cannot currently substantiate them. The historical `published_at` fields describe past metadata, not current publication approval.

## Withdrawn entries

### `dvd-phase1-local-2026-06-27T08-55-16Z`

- Missing: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T08-55-16Z/README.md`
- Missing: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T08-55-16Z/benchmark.json`

### `dvd-phase1-local-2026-06-27T16-06-54Z`

- Missing: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T16-06-54Z/README.md`
- Missing: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T16-06-54Z/PUBLISHED.md`
- Missing: `benchmarks/damn-vulnerable-defi/runs/2026-06-27T16-06-54Z/benchmark.json`

### `sarif-known-findings-2026-06-30T23-48-08Z`

- Missing: `benchmarks/sarif-known-findings/runs/2026-06-30T23-48-08Z/REPORT.md`
- Missing: `benchmarks/sarif-known-findings/runs/2026-06-30T23-48-08Z/PUBLISHED.md`
- Missing: `benchmarks/sarif-known-findings/runs/2026-06-30T23-48-08Z/benchmark.json`
- Missing: `benchmarks/sarif-known-findings/runs/2026-06-30T23-48-08Z/metrics.json`
- Missing: `benchmarks/sarif-known-findings/runs/2026-06-30T23-48-08Z/REGRESSION_REPORT.md`

## Recovery decision

`git log --all -- <referenced path>` returned no file history for the missing records and JSON artifacts in the fetched repository. They were not reconstructed from summary numbers. A fresh local SARIF corpus run was executed separately to validate the getting-started guide; it does not restore or replace any June run.

## Future publication checklist

1. Execute the real benchmark in its authorized scope and preserve the exact environment, command, output, failures, and controls.
2. Review what the run proves: a SARIF pipeline check does not establish exploit impact.
3. Commit each referenced evidence file intentionally. Generated `benchmarks/*/runs/` directories are ignored by default; force-add only reviewed files by exact path, never an entire unreviewed run directory. Exclude secrets, credentials, private target data, and transient databases.
4. Ensure every `record`, `published_record`, `artifact_json`, `metrics_json`, and `regression_report` reference exists in the checkout. Preserve run IDs; do not edit historical timestamps to imitate a new run.
5. Complete independent evidence review before changing the entry to `published` or `verified: true`.
6. Run `python3 scripts/build_pages.py` and `python3 scripts/check_pages.py`; published references with missing files fail validation.

The two remaining published entries have their referenced files present. Availability alone is not a new independent confirmation of their security conclusions.
