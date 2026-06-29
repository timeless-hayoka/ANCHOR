# ANCHOR

Proof-gated smart-contract hunting for authorized security research.

AI says there may be a bug. ANCHOR asks for evidence.

ANCHOR is a local-first proof gate for authorized smart-contract security research. It turns raw tool output into a reproducible case, refuses to promote claims without proof, and preserves the trail from signal to signed evidence.

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).

**Portfolio architecture:** canonical ownership and data flow live in [timeless-hayoka/ARCHITECTURE.md](https://github.com/timeless-hayoka/timeless-hayoka/blob/main/ARCHITECTURE.md). ANCHOR owns benchmarks, outcome ledger, and evidence lifecycle.

## Start here

If you are new to ANCHOR, use this order:

1. [demo/index.html](demo/index.html) - see the product and proof gate quickly
2. [docs/METHODOLOGY.md](docs/METHODOLOGY.md) - understand the hunt workflow
3. [docs/PROOF_GATE.md](docs/PROOF_GATE.md) - understand what counts as a finding
4. [benchmarks/README.md](benchmarks/README.md) - inspect published benchmark artifacts
5. [targets/enzyme-blue.md](targets/enzyme-blue.md) - see the current real-world target note

If you want the short public-facing wording for profiles and outreach, use [docs/PROFILE_COPY.md](docs/PROFILE_COPY.md).

## Core idea

A plausible claim is not a finding.

A claim only moves forward when the evidence holds.

- `signal` -> a scanner, heuristic, or human notices something worth checking
- `hypothesis` -> the possible bug is stated precisely enough to falsify
- `repro_attempted` -> the claim is tested on real code in an authorized environment
- `reproduced_real` -> the impact is demonstrated with a complete proof of concept
- `council_accepted` -> the result survives review and is ready to communicate
- `report_ready` -> the evidence bundle, narrative, and reproduction steps are archived

The point is simple:

- AI says there may be a bug.
- ANCHOR asks for evidence.
- Bad claim fails the gate.
- Real claim reproduces.
- The proof is signed and preserved.

## Methodology

Methodology is a first-class concept in ANCHOR.

The operating sequence is:

1. Scope confirmation
2. Hypothesis creation
3. Evidence collection
4. Reproduction
5. Council review
6. Report generation
7. Archive

Read the method documents here:

- [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PROOF_GATE.md](docs/PROOF_GATE.md)
- [docs/EVIDENCE_LIFECYCLE.md](docs/EVIDENCE_LIFECYCLE.md)
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)

## Benchmarks

Benchmarks exist so other researchers can evaluate ANCHOR by method, not by pitch.

- [benchmarks/README.md](benchmarks/README.md)
- [benchmarks/damn-vulnerable-defi/README.md](benchmarks/damn-vulnerable-defi/README.md)
- [benchmarks/ethernaut/README.md](benchmarks/ethernaut/README.md)
- [benchmarks/openzeppelin/README.md](benchmarks/openzeppelin/README.md)
- [benchmarks/custom/README.md](benchmarks/custom/README.md)
- `benchmarks/index.json` - machine-readable benchmark manifest

Each benchmark records:

- target
- scope
- methodology
- tooling
- detection results
- reproduction results
- false positives
- false negatives
- lessons learned
- evidence artifacts


## Public demo

- [demo/index.html](demo/index.html) - static preview page for researchers, reviewers, and collaborators
- GitHub Pages deployment is defined in `.github/workflows/pages.yml`

## What lives here

- `anchor_server.py` - local run server, SSE event stream, and evidence signing
- `anchor_emit.py` - tiny helper for streaming a real hunt into the console
- `interfaces/static/trinity_hunt.html` - the proof-gate console surface
- `interfaces/static/anchor_dashboard.html` - dashboard companion surface
- `tests/test_anchor_server.py` - server verification
- `BUG_HUNTING_MAP.md` - fast bug-shape map for hunts and reviews
- `TRINITY_RUBRIC.md` - evidence rubric for Trinity decisions
- `HUNT_HYPOTHESIS_TEMPLATE.md` - reusable hunt note for serious leads
- `WEB3_HUNT_MODULES.md` - web3 hunt engines and evidence-gate order
- `docs/ANCHOR_VAULT.md` - durable benchmark roadmap and corpus brief
- `docs/APEX_MOTHERSHIP_INTEGRATION.md` - integration plan for borrowing useful Apex Mothership surfaces
- `docs/APEX_MOTHERSHIP_DASHBOARD_SPEC.md` - concrete dashboard shape for benchmark visibility
- `docs/SCRIPT_REGISTRY_DESIGN.md` - guardrailed helper-script registry design
- `docs/EVIDENCE_STORAGE_INTERFACE.md` - shared evidence-storage contract
- `docs/APEX_MOTHERSHIP_BACKLOG.md` - phased implementation backlog
- `docs/ANCHOR_WORK_QUEUE.md` - current implementation backlog and follow-up tasks
- `docs/ANCHOR_KNOWLEDGE_INGESTION.md` - repo-mining plan for knowledge ANCHOR can reuse
- `outcomes/README.md` - outcome ledger stages tying benchmark evidence to real report outcomes

## Install and run

```bash
./anchor env init
./.venv/bin/pip install -r requirements-dev.txt
./anchor test
uvicorn anchor_server:app --host 127.0.0.1 --port 8000
```

On first start the server creates `anchor_signing_key.pem` with owner-only permissions and reuses it later so evidence signatures stay stable.

## Model backend runtime

ANCHOR now uses a provider-neutral backend layer in `backends/` with a compatibility shim at `backend_runtime.py`.

It exposes:

- `BackendInterface`
- `BackendFactory`
- `OpenAIBackend`
- `OpenAIFirstBackend`
- `OllamaBackend`

The current provider plan is OpenAI-first:

- provider: OpenAI
- API: Responses API
- model: `gpt-5.4-mini` by default
- environment variable: `OPENAI_API_KEY`
- fallback provider: Ollama
- fallback model: `qwen3:4b`
- default Ollama endpoint: `http://127.0.0.1:11434`

```bash
pip install openai
```

Set `ANCHOR_OPENAI_MODEL` if you want to override the default model name. The hunt loop only talks to `BackendInterface`; it does not import OpenAI or Ollama directly.

## Benchmark command

The repo now ships with a single local entrypoint that prefers `./.venv/bin/python` when it exists and otherwise falls back to `python3`.

```bash
./anchor benchmark dvd phase1
```

For a structured hunt plan from a target note:

```bash
./anchor hunt plan --target targets/enzyme-blue.md
```

The benchmark command writes a fresh benchmark artifact under `benchmarks/damn-vulnerable-defi/runs/` and updates `benchmarks/index.json` so the latest summary shows up in the demo surfaces. The hunt plan command turns a target note into a structured, falsifiable queue.

For passive GitHub repository intelligence and attack-surface triage:

```bash
./anchor github crawl --query "smart contract security fuzzing" --query "solidity foundry echidna"
```

That command writes a clean discovery bundle under `discoveries/github/` with one folder per candidate repo, a compact pre-hunt brief, and machine-readable JSON you can sort through before turning anything into a hunt, issue, or PR. It stays on public metadata and public code signals, so it can rank repos, explain why they look interesting, and record the authorization posture without moving into exploitation.

The supported default command is `./anchor github crawl`.

To approve a repo into the human queue without mutating the discovery evidence:

```bash
./anchor github select perimetersec/fuzzlib
```

To generate the constrained hunt plan for a selected repo:

```bash
./anchor github plan perimetersec/fuzzlib
```

The plan command reads `selected/<repo>/selection.json` and `candidate.json`, then writes `hunt_plan.json` and `hunt_plan.md` next to the selected repo. It does not clone, scan, open issues, or contact maintainers.

It also creates `scope_confirmation.md` as a human-filled gate. Until that file says `authorized`, the selected repo remains plan-only.

To check the scope gate:

```bash
./anchor github scope-check perimetersec/fuzzlib
```

That command should report `Scope status: NOT AUTHORIZED` until `scope_confirmation.md` is filled in and the reviewer decision is `authorized`.

## Connect the console

Open the console, set the server URL to `http://127.0.0.1:8000`, and connect the Live Run tab. The event stream should climb through `run.started -> case.started -> stage.started -> finding.detected -> finding.correlated -> poc.result -> case.completed -> run.completed`.

## Notes

- This repo is the flagship.
- `infj_bot` is the companion layer and internal reasoning surface.
- `AI-Forge-Protocol`, `bounty-bot`, and `apex-mothership` are supporting projects in the same ecosystem.
- The public story stays honest: tamper-evident local signing, not legal chain-of-custody claims.

## Phase 2 target

- Program: [Enzyme Blue](https://immunefi.com/bug-bounty/enzymefinance/scope/#impacts)
- Target: `UnpermissionedActionsWrapper`
- Hunt note: [targets/enzyme-blue.md](targets/enzyme-blue.md)

That is the first real-world reproduction target because it has a clear authorization boundary and a reviewer-friendly proof-of-concept path.


## Benchmark history

```bash
anchor benchmark history --limit 5
```

This prints the latest published benchmark runs with pass/fail/timeout counts, detector signal count, and scoped medium/high target-relevant detector findings.
