# DeFiHackLabs Source-Tool Comparison

## Target

A curated DeFiHackLabs subset used to compare ANCHOR against a recorded source-tool baseline.

## Scope

Authorized local benchmark only. This corpus is for method validation and side-by-side comparison, not live exploitation.

## Methodology

Use ANCHOR to test the same curated cases against a source-tool reference baseline and record where ANCHOR is stronger, weaker, or aligned.

## Tooling

- ANCHOR SARIF pipeline
- reference source-tool labels (slither)
- benchmark report generation

## Detection results

The benchmark records ANCHOR visibility, source-tool visibility, and the delta between them.

## Reproduction results

Each case keeps a single reproducible evidence bundle and a source-tool comparison path.

## False positives

Cases where the source-tool flags noise but ANCHOR suppresses it are recorded here.

## False negatives

Cases where ANCHOR misses a curated positive are recorded here.

## Lessons learned

A comparison benchmark is only useful if both the ANCHOR path and the source-tool baseline are visible in the report.

## Evidence artifacts

- [corpus.json](inputs/corpus.json)
- [expectations.json](expected/expectations.json)
- [run_source_tool_comparison.py](run_source_tool_comparison.py)

## Compare path

Each run writes:

- `benchmark.json`
- `metrics.json`
- `source_tool_metrics.json`
- `source_tool_compare.json`
- `REPORT.md`

## Run

```bash
anchor benchmark defihacklabs source-comparison
```
