# DeFiHackLabs Source-Tool Comparison Report - 2026-06-29T18:46:05.060643+00:00

- Benchmark ID: `defihacklabs-source-comparison`
- Run ID: `defihacklabs-source-comparison-2026-06-29T18-46-05Z`
- Corpus: `benchmarks/defihacklabs/source-comparison/inputs/corpus.json`
- Expectations: `benchmarks/defihacklabs/source-comparison/expected/expectations.json`
- Benchmark JSON: `benchmarks/defihacklabs/source-comparison/runs/2026-06-29T18-46-05Z/benchmark.json`
- Metrics JSON: `benchmarks/defihacklabs/source-comparison/runs/2026-06-29T18-46-05Z/metrics.json`
- Source Tool Metrics JSON: `benchmarks/defihacklabs/source-comparison/runs/2026-06-29T18-46-05Z/source_tool_metrics.json`
- Source Tool Compare JSON: `benchmarks/defihacklabs/source-comparison/runs/2026-06-29T18-46-05Z/source_tool_compare.json`

## Anchor Summary
- cases: 5
- passed: 4
- failed: 1
- true_positives: 3
- false_positives: 1
- false_negatives: 0
- true_negatives: 1
- duplicates_removed: 1
- precision: 0.75
- recall: 1.0
- f1: 0.8571

## Source Tool Comparison
- source_tool: `slither`
- anchor_visible: `4`
- source_tool_visible: `4`
- shared_visible: `3`
- anchor_only: `1`
- source_only: `1`
- agreement: `3`
- visible_delta: `0`

## Cases

### duplicate-owner-check
- status: `PASSED`
- anchor_classification: `TP`
- expected_visible: `True`
- anchor_visible: `True`
- source_tool_visible: `True`
- comparison: `shared_visible`
- note: A real source finding should survive normalization and deduplication as one visible issue.
- raw_findings: `2`
- unique_findings: `1`
- duplicates_removed: `1`
- actual_findings: `slither:missing-onlyowner:src/OwnableVault.sol:42`

### halmos-balance-invariant
- status: `PASSED`
- anchor_classification: `TP`
- expected_visible: `True`
- anchor_visible: `True`
- source_tool_visible: `True`
- comparison: `shared_visible`
- note: Proof-gate findings should be promoted by the SARIF pipeline.
- raw_findings: `1`
- unique_findings: `1`
- duplicates_removed: `0`
- actual_findings: `halmos:halmos-balanceConservation:src/Bank.sol:12`

### generic-source-warning
- status: `FAILED`
- anchor_classification: `FP`
- expected_visible: `False`
- anchor_visible: `True`
- source_tool_visible: `True`
- comparison: `shared_visible`
- note: A low-signal source finding should remain a visible false positive for the benchmark.
- raw_findings: `1`
- unique_findings: `1`
- duplicates_removed: `0`
- actual_findings: `slither:unchecked-call:src/Vault.sol:88`

### reentrancy-benign-miss
- status: `PASSED`
- anchor_classification: `TP`
- expected_visible: `True`
- anchor_visible: `True`
- source_tool_visible: `False`
- comparison: `anchor_only`
- note: A known issue in protected code should still be counted if the corpus expects it to stay visible.
- raw_findings: `1`
- unique_findings: `1`
- duplicates_removed: `0`
- actual_findings: `slither:reentrancy-benign:src/ProtectedVault.sol:101`

### source-tool-only-noise
- status: `PASSED`
- anchor_classification: `TN`
- expected_visible: `False`
- anchor_visible: `False`
- source_tool_visible: `True`
- comparison: `source_only`
- note: The source baseline records a visible issue, but ANCHOR suppresses the empty/noisy signal.
- raw_findings: `0`
- unique_findings: `0`
- duplicates_removed: `0`
- actual_findings: `—`

## Evidence
- inputs: `benchmarks/defihacklabs/source-comparison/inputs/corpus.json`
- expectations: `benchmarks/defihacklabs/source-comparison/expected/expectations.json`
- manifest: `benchmarks/index.json`
- source_tool_compare: `benchmarks/defihacklabs/source-comparison/runs/2026-06-29T18-46-05Z/source_tool_compare.json`
