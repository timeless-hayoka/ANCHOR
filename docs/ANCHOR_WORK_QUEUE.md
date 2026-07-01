# ANCHOR Work Queue

> Only work that can be executed, tested, and evidenced belongs here.

## Active

### A-001 — Benchmark the SARIF pipeline against known findings

**Status:** COMPLETE

**Goal**
Run ANCHOR's SARIF ingest, normalization, deduplication, validation, and reporting flow against a known benchmark corpus.

**Why it matters**
ANCHOR is only useful if its findings can be measured for signal quality, reproducibility, and analyst usefulness.

**Progress (2026-06-30)**

- Corpus: `benchmarks/sarif-known-findings/` (4 labeled cases)
- CLI path: `./anchor benchmark sarif known-findings`
- Latest run: `sarif-known-findings-2026-06-30T23-48-08Z`
- Measured: **TP=3, FP=0, FN=0, TN=1**, precision=1.0, recall=1.0
- Published baseline: `sarif-known-findings-2026-06-30T23-48-08Z` (`publication_tier: published`)
- Merge: PR #13 → `main` at `b16e92e`

**Acceptance criteria**

* [x] At least one benchmark corpus is selected and documented.
* [x] SARIF artifacts are ingested through the normal CLI or server path.
* [x] A benchmark run writes results under `benchmarks/<name>/runs/`.
* [x] Results record true positives, false positives, false negatives, and duplicates removed.
* [x] Runtime and environment details are captured.
* [x] A summary report is written to `benchmarks/<name>/REPORT.md`.
* [x] Tests still pass using:

  ```bash
  python3 -m pytest -q tests/test_anchor_cli.py tests/test_anchor_server.py tests/test_anchor_sarif.py
  ```
* [x] Publish a baseline run to `published` tier (`./anchor benchmark publish sarif-known-findings-2026-06-30T23-48-08Z`)

**Evidence required**

* Input SARIF files or reproducible download instructions
* Raw run output
* Final benchmark report
* Test output
* Git commit hash

**Next smallest action**
Choose one small, public benchmark corpus with known expected findings and create:

```text
benchmarks/<benchmark_name>/
├── README.md
├── inputs/
├── expected/
└── REPORT.md
```

**Blocked by**

* None

---

## Ready

### A-002 — Make benchmark results machine-readable

**Status:** QUEUED

**Goal**
Export benchmark metrics as JSON so regressions can be compared automatically.

**Acceptance criteria**

* [ ] Produce `metrics.json` per benchmark run.
* [ ] Include TP, FP, FN, TN, precision, recall, F1, runtime, and tool versions.
* [ ] Add a test validating the schema.

---

### A-003 — Add regression comparison

**Status:** QUEUED

**Goal**
Compare a new benchmark run against a baseline and flag meaningful degradation.

**Acceptance criteria**

* [ ] Baseline metrics can be stored.
* [ ] CLI reports metric deltas.
* [ ] Configurable threshold fails the run when precision or recall drops.

---

## Blocked

*None.*

---

## Completed

### A-000 — SARIF pipeline and benchmark workspace

**Status:** COMPLETE

**Evidence**

* Commit: `e1af9f1`
* Tests: `44 passed, 1 skipped`
* Verified via `python3 -m pytest`
* Generated benchmark runs and Chroma data ignored
