# Deployment evidence → Trinity handoff

**Contract:** Research-signal creation only. This route cannot issue a scope grant, execute a test, enter `reproduced_real`, or produce a bounty report.

## Inputs

Use the JSON result from `scripts/anchor_hunt_readiness.py` and a source evidence report from the corresponding deployment, such as `scripts/check_extra_lendingpool_source.py`. The handoff rejects mismatched chain IDs, deployed contract addresses, unpinned revisions, contradictory gate states, and suspicious claims of reproduction or authorization.

```bash
python scripts/anchor_trinity_handoff.py \
  --readiness evidence/extra-hunt-readiness.json \
  --source-evidence evidence/extra-lendingpool-source-verification.json \
  --output evidence/extra-trinity-signal.json
```

The command returns 0 when it **successfully creates a signal**, even if the signal is deliberately blocked for research. It returns 2 on invalid or contradictory inputs. It never overwrites an existing output file. All inputs are treated as untrusted snapshots, not proof that their claimed content was independently verified.

## Output

The artifact contains:

- A Trinity `LeadRecord` using the project's real state-machine schema, always in `signal` state, `scope_status: unknown`. No fabricated claim, proof, reviews or timestamps.
- A deterministic lead ID from the pinned repository commit, chain ID and contract address.
- A provenance block with SHA-256 hashes of canonical JSON readiness and source reports. Hashes provide **integrity references**, not independent evidence authenticity.
- Exact labels `deployment_bytecode_equivalence: NOT_PROVEN`, `reproduction: NOT_ATTEMPTED`, `finding: NONE`, and `authorization_grant_issued: false`.
- One of `BLOCKED_RESEARCH_SIGNAL` or `SOURCE_REVIEW_ONLY` as the handoff status. Neither is permission to actively test or an accepted finding.

## Actual Extra Finance acceptance case

The `Extra Finance source evidence` GitHub Actions job fetches public Sourcify metadata and the pinned source, generates a **BLOCKED** readiness report, and feeds both to this bridge. It requires the resulting Trinity signal to remain blocked and unauthorised. That is the **expected** healthy outcome while scope evidence, source version matching and full deployed-bytecode comparison remain unresolved.

The separately passing 14/14 Foundry tests refer to the pinned GitHub source. They do **not** validate the different Sourcify verified source.

## Remaining launch gates

To move a Trinity lead beyond `signal`, obtain an operator-approved matching scope grant from the existing scope checker, link the verified deployed implementation and complete compilation inputs, reproduce a distinct hypothesis locally in an isolated Foundry environment with both positive and negative controls, then run independent Watcher and Council validation. Use `apply_transition` with real evidence; this handoff deliberately does not invoke it.

**This is integration progress, not a vulnerability discovery.**
