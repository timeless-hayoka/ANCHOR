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

- anchor_sarif pipeline
- slither-compatible SARIF payloads
- aderyn adapter inputs
- mythril adapter inputs
- halmos invariant inputs

## Detection results

Pending benchmark record population.

## Reproduction results

Pending benchmark record population.

## False positives

Pending benchmark record population.

## False negatives

Pending benchmark record population.

## Lessons learned

Use this benchmark to measure whether ANCHOR keeps the findings we want and filters the noise we do not.

## Evidence artifacts

- [inputs/corpus.json](inputs/corpus.json)
- [expected/expectations.json](expected/expectations.json)
- [REPORT.md](REPORT.md)
