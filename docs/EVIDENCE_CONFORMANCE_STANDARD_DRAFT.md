# ANCHOR evidence conformance standard — draft v0.1

Status: **PROPOSED / UNVALIDATED**. This is a proposed testable engineering contract, not a certification, security guarantee, or industry standard.

## Purpose
A system may promote a security hypothesis to a verified finding only when it can present reproducible, scoped, independently reviewable evidence. AI confidence or persuasive narrative is not evidence.

## Authority boundaries
- **ANCHOR**: sole authority to promote evidence states and record signed outcomes.
- **AI-Forge-Protocol**: code/patch validation worker; results are advisory inputs, never self-promoting evidence.
- **DRIFT**: memory, retrieval and reasoning support; memories and model output cannot override proof or authorization gates.
- **Human operator**: confirms target authorization, reviews consequential findings and controls publication.

## Mandatory states
`SIGNAL -> HYPOTHESIS -> REPRO_ATTEMPTED -> REPRODUCED_REAL -> COUNCIL_ACCEPTED -> REPORT_READY`.

Additional terminal or non-promoting states: `REJECTED`, `BLOCKED`, `INCONCLUSIVE`. A skipped or timed-out check must not become `REPRODUCED_REAL`.

## Affirmative conditions (all required before promotion)
A1. **Authorization**: exact asset, permitted methods, program scope, and current authorization evidence are recorded; missing or stale scope fails closed.
A2. **Pinned inputs**: repository commit SHA, tool versions, environment, and relevant configuration are recorded.
A3. **Reproducible proof**: a deterministic, isolated PoC or equivalent experiment executes with explicit assertions of the claimed impact.
A4. **Negative control**: patched or nonvulnerable equivalent does not reproduce the claimed impact; when impossible, mark the limitation and do not claim fully verified.
A5. **Independent challenge**: a distinct review stage challenges the hypothesis and examines alternative explanations.
A6. **Integrity**: evidence is tamper-evident, linked to inputs and outputs, and cannot be replaced without detection.
A7. **Failure discipline**: timeout, missing RPC, dependency failure, model uncertainty, or absent evidence produces BLOCKED/INCONCLUSIVE/REJECTED, never PASS.
A8. **Human review**: release or external disclosure requires explicit authorized human approval.

## Conformance tests to implement (not yet executed)
| ID | Stimulus | Required result |
| --- | --- | --- |
| C01 | Valid authorized known-vulnerable contract + reproducing assertion | Eligible for promotion only after A1-A8 |
| C02 | Same contract after patch | No reproduced-real promotion |
| C03 | Fabricated AI finding without PoC | Reject or hold as hypothesis |
| C04 | PoC test passes but assertion does not demonstrate impact | Reject promotion |
| C05 | Out-of-scope target or expired authorization | Block before investigation |
| C06 | Missing RPC / timeout / missing dependency | BLOCKED, not PASS |
| C07 | Altered evidence after signing | Signature/integrity verification fails |
| C08 | Forge reports success while its subprocess exits nonzero | Reject promotion |
| C09 | DRIFT memory asserts a vulnerability contradicted by test | Test evidence controls outcome |
| C10 | Identical pinned run repeated | Consistent verdict and explainable differences |

## Evaluation record format
For each test: test_id, run_id, commit_sha, UTC timestamp, platform/runtime, tool versions, scope evidence, input hashes, expected outcome, observed outcome, exit code, artifacts, verdict (PASS/FAIL/BLOCKED), reviewer.

## Release gates
- G0: repository and dependencies can be installed in a fresh environment; no committed secrets.
- G1: baseline tests execute with a published failure inventory; no concealed failures.
- G2: C01-C10 are implemented and pass in isolated environments; test harness self-test catches planted failures.
- G3: Forge and DRIFT integration contracts pass both happy-path and fail-closed tests.
- G4: independent clean-room reproduction succeeds using pinned dependencies and public instructions.
- G5: release claims are limited to the measured scope and published results.

## Ordered execution
1. Record baseline branch, SHA, Python/Foundry versions and dependencies.
2. Execute existing pytest suite and four ANCHOR CLI commands.
3. Implement C03-C07 negative/failure tests before adding new capabilities.
4. Execute known-vulnerable and patched controls in isolated Foundry environment.
5. Test Forge integration, then DRIFT integration.
6. Independently reproduce, publish limitations, and consider release.

No tests were executed by the act of creating this document.
