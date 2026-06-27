# Benchmarks

Benchmarks let other researchers evaluate ANCHOR by outcome and method.

## Purpose

Each benchmark answers:

- what was tested
- how it was tested
- what was detected
- what reproduced
- what failed to reproduce
- what the system learned

## Required sections

Every benchmark record should include:

- Target
- Scope
- Methodology
- Tooling
- Detection results
- Reproduction results
- False positives
- False negatives
- Lessons learned
- Evidence artifacts

## Current benchmark families

- [damn-vulnerable-defi](damn-vulnerable-defi/README.md)
- [ethernaut](ethernaut/README.md)
- [openzeppelin](openzeppelin/README.md)
- [custom](custom/README.md)

## Interpretation rule

A benchmark win is not a meaningful signal unless the reproduction result is clear.

Detection-only numbers are useful, but reproduction is what makes the benchmark persuasive.

## Standard benchmark format

Every benchmark should converge on the same structure:

- Metadata
- Target
- Scope
- Environment
- Tool Versions
- Methodology
- Results
- Reproduction
- Evidence
- Limitations
- Lessons Learned
- Next Actions

## Benchmark levels

| Level | Meaning |
| --- | --- |
| Phase 0 | Baseline documentation and methodology |
| Phase 1 | Detection benchmark |
| Phase 2 | Reproduction benchmark |
| Phase 3 | Comparative benchmark |
| Phase 4 | Regression suite |

## Manifest

The machine-readable registry is stored in `benchmarks/index.json`.

## Publication policy

Successful reruns are kept on disk for traceability, but they are not all treated as first-class benchmark artifacts.

- `development`: successful internal reruns kept for engineering history and comparison
- `published`: intentionally promoted benchmark artifacts that show up by default in history and demo fallback views

This gives ANCHOR two things at once:

- honest internal repetition
- a cleaner public benchmark record

Promote a run when it is the one you want people to cite or compare against.

```bash
anchor benchmark publish <run_id> --note "phase1 baseline"
```

## Benchmark history

```bash
anchor benchmark history --limit 5
```

This prints the latest published benchmark runs with pass/fail/timeout counts, detector signal count, and scoped medium/high target-relevant detector findings.

To include successful development reruns as well:

```bash
anchor benchmark history --all --limit 10
```

## Benchmark compare

```bash
anchor benchmark compare <run_a> <run_b>
```

This reports run-to-run deltas for:

- pass/fail/timeout counts
- raw detector findings
- target-relevant detector findings
- medium/high target-relevant findings
- detector provenance shifts

## Outcome ledger

Benchmarks are only half the story. The outcome ledger is where benchmark evidence meets real-world report handling.

```bash
anchor outcome history --limit 10
anchor outcome record --stage accepted --target enzyme --run-id <run_id> --report-id immunefi-123 --note "accepted for payout review"
```

Suggested stages:

- `benchmark_published`
- `report_submitted`
- `triaged`
- `accepted`
- `rejected`
- `patched`
- `merged`
