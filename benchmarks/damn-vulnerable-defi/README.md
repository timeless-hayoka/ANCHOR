# Damn Vulnerable DeFi

## Target

Damn Vulnerable DeFi challenge set used as a controlled benchmark corpus.

## Scope

Authorized local benchmark only. This is a training and evaluation target, not a live bounty target.

## Methodology

Use ANCHOR to:

- classify challenge behavior
- detect plausible issues
- attempt reproduction with complete tests
- record detection-to-reproduction gaps

## Tooling

- slither
- mythril
- echidna
- medusa
- forge

## Detection results

Pending benchmark record population.

## Reproduction results

Pending benchmark record population.

## False positives

Pending benchmark record population.

## False negatives

Pending benchmark record population.

## Lessons learned

Use this benchmark to tune proof-gate discipline, not just detector coverage.

## Evidence artifacts

Store run notes, registry outputs, and signed evidence references here as the benchmark matures.

## Challenge expectations

- [challenge_expectations.json](challenge_expectations.json)

The expectation file gives future runs a stable comparison contract: expected ground truth, expected Phase 1 outcome, and per-challenge notes.

## Fork RPC (puppet-v3, curvy-puppet)

These challenges fork mainnet at historical blocks and require an **archive-capable** RPC endpoint.

1. Copy [env.example](env.example) to your DVD checkout as `.env` (or export `MAINNET_FORKING_URL`).
2. PublicNode’s free endpoint without a token returns HTTP 403 for archive state — add a personal token from https://www.allnodes.com/publicnode
3. Verify from ANCHOR:

```bash
./anchor env fork-check
```

4. Re-run Phase 1:

```bash
./anchor benchmark dvd phase1
```

Benchmark logs label RPC failures as `archive_token_required` when PublicNode blocks historical state.

## Benchmark records

- [2026-06-26 Phase 0 baseline](2026-06-26-phase0-baseline.md)
- [2026-06-26 Phase 1 scaffold run](runs/2026-06-26T18-59-25Z/README.md)
- [2026-06-26 Phase 1 scaffold run with expectations](runs/2026-06-26T23-14-42Z/README.md)

## Archive

Interrupted benchmark attempts are preserved under [../archive/incomplete](../archive/incomplete) for traceability. They are not valid benchmark results.
