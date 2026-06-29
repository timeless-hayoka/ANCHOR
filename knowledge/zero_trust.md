# Proof Gates & Zero-Trust Promotion

## Rule

> Trinity may suggest. Forge must reproduce. Council must approve framing. Vault must archive.

No component skips another on the promotion path.

## Validator bridge

`anchor_sarif/validator_bridge.py` — `validate_candidate(finding)` returns:

| Field | Meaning |
| --- | --- |
| `status` | promote \| review \| reject |
| `confidence` | 0–1 blended signal + economic relevance |
| `future_relevance_score` | hypothesis usefulness under stated future protocol |
| `economic_impact_score` | sensitivity to economic/MEV context |
| `mev_sensitivity_score` | MEV-lifecycle alignment |

## Confidence model (implementation)

```text
confidence = max(signal_confidence, future_relevance_score)

if fp_heuristics.suggested_action == promote OR economic.decision == promote:
    status = promote
elif fp_heuristics drop AND economic.decision == reject:
    status = reject
else:
    status = review
```

Tune thresholds via `discard_threshold` (default 0.7) in validator calls—not in the UI.

## Zero-trust checks before ledger write

1. Finding has stable `dedup_key` and source artifact path.
2. ValidationDecision attached (even if `review`).
3. Reproducibility state recorded if claiming exploitability.
4. Outcome event uses structured `links` to benchmark/artifact/pr/issue.
5. Signed bundle optional but recommended for external disclosure.

## What models must not do

- Auto-set `status: accepted` from chat completion text.
- Upgrade severity based on narrative alone.
- Omit negative results (failed repros must be logged).

## Operator escape hatch

`anchor outcome add` — manual ledger entry still requires explicit type/status; use for external submissions with artifact links.
