# Phase 2 — first implementation batch

Authorization: the owner approved the Phase 1 ranked fix order on November 6,
2026. This branch starts that work; it does not complete Phase 2.

## Delivered

1. Live run claims cannot manufacture successful execution artifacts or proof
   states. Accuracy without ground truth is unknown. Registry output must be
   fresh and bind to the run/target, subprocess failure is terminal, and finished
   runs cannot be mutated. Fourteen regression cases failed on the original
   implementation before these fixes.
2. Demo runs require explicit selection and carry fixture provenance. Case
   lookup has no specimen fallback; session/chat/signature responses identify
   their actual limitations. No-op CLI commands return unsupported errors.
   Deterministic SARIF processing works without optional ML packages, and the
   separate research command no longer crashes on missing parser attributes.
3. Producer telemetry requires a per-run token and cannot control run lifecycle.
   Browser origins and request size are constrained. Helpers have bounded
   execution/output, credential-free environments, and process-group cleanup.
   Script authorization uses canonical paths; source/registry reads reject
   symlink traversal. Repository identity rejects modified, untracked and
   ignored content. Target Forge execution requires Linux bubblewrap isolation
   and never falls back to the host. Inspection without fresh analysis returns
   partial output and a nonzero CLI status, not a successful scan.

## Verified locally

Python 3.12.14; requirements installed in the isolated audit environment.

```text
python -m pytest tests/ -vv --junitxml=phase2-tests-final.xml
483 passed, 1 skipped, 30 subtests passed in 9.84s
```

The skipped test requires an OpenAI API key. No new provider call was made.
The 34 new cases include real bounded subprocess execution and explicitly
synthetic producer/registry controls; they are not Solidity exploit tests.

```text
python scripts/build_pages.py
python scripts/check_pages.py
PASS: console startup, 10 views, CVSS known/zero-impact vectors, case report,
      untested-state accounting, local chat
PASS: 4 pages, 3 scripts, all static links, published benchmark packaging,
      no backend routes

python anchor_cli.py benchmark sarif known-findings
python scripts/verify_sarif_benchmark.py
PASS: 4 labeled cases; no FP/FN; positive and negative controls verified
```

These checks validate processing and behavior, not fresh detector discovery.
Generated benchmark metadata was restored after execution; it is not part of
the implementation diff.

## Not yet delivered / known limits

- No new Slither/Mythril/Semgrep/Echidna installation or source-to-detector
  execution; native unsupported output handling and ingestion still need work.
- No fresh Solidity detector-to-Foundry proof demonstration, fuzz campaign, or
  production contract finding. The current BugBot analyzer deliberately reports
  partial status until real analysis is connected.
- Bubblewrap exists here but namespace creation fails with
  `bwrap: open /proc/5/ns/ns failed: No such file or directory`. The fail-closed
  path is tested; successful sandboxed target execution is **not** verified in
  this hosted environment. Forge/solc/scanner executables are unavailable here.
- System libraries and explicitly selected workspace are visible inside the
  target sandbox. Required compiler/tool assets must be configured there.
  Trusted Python helpers have resource limits, not OS sandbox isolation.
- General API session authentication, stable signing-key failure handling,
  dependency locking, lint/type CI, persistent run storage, and complete server
  module extraction remain unfinished. The service is for trusted local use,
  not exposure to a network or multiple users.
- Main CLI clustering/tuning/visualization and standalone telemetry run creation
  explicitly report unsupported rather than pretending to execute.
- Live server proof promotion is intentionally unavailable. Imported artifacts
  are retained as claims until an independently verified executor is connected.

Next: review this batch, then implement one sandboxed local-project Slither
execution path with strict output parsing, preserved provenance, vulnerable and
repaired controls, and a clearly separated Foundry reproduction step. Ask the
owner before paid services or large dependency installations. Do not merge
automatically.
