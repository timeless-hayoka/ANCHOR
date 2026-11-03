# ANCHOR hunt readiness — operator guide

**Purpose:** An evidence-gated handoff from passive Finder discovery to review of a particular source revision and deployed contract. A green CI job or Finder score is **not** bounty authorization, source equivalence, exploitability, or a reportable finding.

## Stages and what they mean

| Stage | Required evidence | Blocks when |
| --- | --- | --- |
| Identity | Exact `owner/repository` and immutable 40-character commit SHA | Branch/tag or malformed identity |
| Passive discovery | A `bundle.json` with exactly one matching `complete` candidate | Scan incomplete, metadata-only, missing, ambiguous |
| Scope | Reviewer-approved `scope_confirmation.md`, evidence file, matching repo URL and commit, permitted `analysis` | No approval, expired grant, missing proof, mismatch or denial |
| Source file | Source verification output for the **same chain/address**, with `PINNED_SOURCE_MATCH`, Sourcify `exact_match`, matched source paths and SHA256 | Source drift, non-exact runtime, wrong chain/address, malformed output |

The CLI **never writes an operational grant**. A passed result is labeled `SOURCE_REVIEW_GATES_PASSED`, not `READY_FOR_LIVE_TESTING`. Full compilation and deployed-bytecode parity, isolated Foundry reproduction, independent Trinity review and bounty eligibility are **separate, unproven stages** until individually validated.

## Running an evidence check

```bash
python scripts/anchor_hunt_readiness.py \
  --target-id owner/repository \
  --target-ref FULL_40_CHARACTER_GIT_SHA \
  --chain-id 10 \
  --contract-address 0xCONTRACT_ADDRESS \
  --discovery-bundle discoveries/github/RUN_ID/bundle.json \
  --scope-confirmation discoveries/github/RUN_ID/selected/owner-repository/scope_confirmation.md \
  --source-evidence evidence/verified-source.json \
  --output evidence/hunt-readiness.json
```

Use the exact target-specific verified-source report. Do not create or alter authorization records merely to make the gate pass. The existing `anchor bugbot scope-check` remains a separate operator-controlled issuance step.

The command exits `0` only when all four *source-review* gates pass and `2` on insufficient, missing or contradictory evidence. It prints a stage-by-stage JSON report and a clear statement that full deployed equivalence and reproducibility were **not** established.

## Extra Finance current example

The workflow `.github/workflows/extra-finance-source-evidence.yml` collects the read-only Sourcify source report for ExtraFi's Optimism LendingPool and runs this gate. It does **not** supply a reviewed Finder bundle or scope confirmation. Additionally, the pinned GitHub `LendingPool.sol` differs from Sourcify's verified file. The correct outcome is `BLOCKED`; GitHub Actions should record that report as evidence, **not** call it a vulnerability or a verified deployment.

Foundry's pinned-source 14/14 baseline tests remain valuable local controls, but they do not reproduce behavior in the different verified deployed-source revision.

## Additional launch requirements

Before ANCHOR can be called fully operational on a live bounty target, validate the entire asset/scope-to-implementation mapping, exact build settings and linked dependencies, authorized isolated reproduction, negative controls, independent Watcher/Council review, report confidentiality, and repeatable source-to-evidence provenance. CI passing by itself is insufficient.

To extend this gate, add *measured* evidence for those stages rather than mapping a label or boolean from a report to `REPRODUCED_REAL`.
