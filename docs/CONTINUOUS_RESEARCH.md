# ANCHOR continuous research and three-check finding gate

## Automated jobs
The `ANCHOR continuous evidence` GitHub Actions workflow runs daily at 09:17 UTC and can be manually dispatched. It executes the Python regression suite, a labeled SARIF known-findings benchmark, and a **separate passive public-repository discovery** job. Both jobs upload evidence, including on failure. A successful job is not a claim of a newly discovered vulnerability.

Discovery produces **candidates only**. Public code availability is not authorization to perform active testing. A human must verify the target identity, bug-bounty scope, applicable exclusions, and authorization before any active tests. No scheduled job selects targets, executes exploit PoCs against live deployments, or submits reports.

## Mandatory triple verification for any finding
A finding must remain `UNCONFIRMED` unless all three checks are independently evidenced:

1. **Scope and identity:** Preserve the program policy/version, in-scope address or repository commit, network, authorization evidence, and exclusions. Fail closed when unknown.
2. **Independent reproduction:** Execute a minimal deterministic PoC on an authorized local test deployment or approved fork, with a failing precondition and a passing exploit assertion. Repeat from a clean state and preserve exact commands, tool versions, commit, inputs, outputs, and hashes. An AI-generated hypothesis alone is not reproduction.
3. **Adversarial review and impact:** Have a second independent test or reviewer attempt to falsify the exploit, distinguish expected behavior from a vulnerability, verify attacker prerequisites, and substantiate realistic impact. Re-run regression after a proposed fix.

Only when all three are documented may a reviewer promote a case to `REPRODUCED_REAL` for the exact validated context. Promotion does not imply bounty eligibility, deployed exploitability, or financial impact. A failed check returns the case to hypothesis/hold; no automatic report publication or submission.

## Next release gates
- Confirm the scheduled workflow passes in GitHub Actions; inspect any failures and repair without weakening tests.
- Add a separate Foundry CI job against explicitly checked-in, self-contained local lab fixtures; require `forge test` assertions and archive reproducible outputs. Never require production RPC secrets for the baseline.
- Add benchmark trend comparisons and fail on material precision/recall regression only after baseline semantics are verified.
- Keep vulnerability reports private until disclosure authorization and evidence review are complete.
