# SARIF Known Findings

## Target

ANCHOR's SARIF processing pipeline evaluated against a small known-findings corpus.

## Scope

Authorized local benchmark only. This corpus is for signal-quality measurement, not for live target testing.

## Methodology

Use ANCHOR to:

- ingest known findings through the normal SARIF pipeline
- normalize and deduplicate cross-tool reports
- apply signal filtering
- measure visible findings against the expected corpus labels
- record true positives, false positives, false negatives, and duplicates removed

## Tooling

- `anchor_sarif` pipeline
- slither-compatible SARIF payloads
- aderyn adapter inputs
- mythril adapter inputs
- halmos invariant inputs

## Run command

```bash
./anchor benchmark sarif known-findings
```

Optional publish after review:

```bash
./anchor benchmark publish sarif-known-findings-2026-06-30T19-17-27Z
```

## Latest measured results

**Run:** `sarif-known-findings-2026-06-30T23-48-08Z` (A-001 baseline after generic unchecked-call filter)

| Metric | Value |
|--------|-------|
| Cases | 4 |
| Passed | 4 |
| Failed | 0 |
| True positives | 3 |
| False positives | 0 |
| False negatives | 0 |
| True negatives | 1 |
| Duplicates removed | 1 |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 | 1.0 |

### Case outcomes

| Case | Result | Notes |
|------|--------|-------|
| `duplicate-owner-check` | TP | Dedup collapsed two tool reports to one visible finding |
| `halmos-balance-invariant` | TP | Halmos invariant surfaced correctly |
| `generic-source-warning` | TN | Generic Slither `unchecked-call` discarded without exploit context |
| `reentrancy-benign-miss` | TP | Cross-function reentrancy visible despite guard snippet |

## Lessons learned

- Dedup and normalization behave on multi-tool duplicate owner checks.
- Generic Slither `unchecked-call` warnings with only “Low-level call may be unsafe” are filtered; exploit-context messages still promote.
- Cross-function reentrancy case documents guard-snippet dismissal behavior with fix hint in run report.

## Evidence artifacts

- [inputs/corpus.json](inputs/corpus.json)
- [expected/expectations.json](expected/expectations.json)
- [REPORT.md](REPORT.md)
- Latest run: [runs/2026-06-30T19-17-27Z/REPORT.md](runs/2026-06-30T19-17-27Z/REPORT.md)
