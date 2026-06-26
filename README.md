# ANCHOR

Proof-gated smart-contract hunting for authorized security research.

AI says there may be a bug. ANCHOR asks for evidence.

ANCHOR is a local-first proof gate for authorized smart-contract security research. It turns raw tool output into a reproducible case, refuses to promote claims without proof, and preserves the trail from signal to signed evidence.

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

## Install and run

```bash
pip install -r requirements.txt
uvicorn anchor_server:app --host 127.0.0.1 --port 8000
```

On first start the server creates `anchor_signing_key.pem` with owner-only permissions and reuses it later so evidence signatures stay stable.

## Connect the console

Open the console, set the server URL to `http://127.0.0.1:8000`, and connect the Live Run tab. The event stream should climb through `run.started -> case.started -> stage.started -> finding.detected -> finding.correlated -> poc.result -> case.completed -> run.completed`.

## Notes

- This repo is the flagship.
- `infj_bot` is the companion layer and internal reasoning surface.
- `AI-Forge-Protocol` and `bounty-bot` are supporting evidence that the gate generalizes.
- The public story stays honest: tamper-evident local signing, not legal chain-of-custody claims.

## Phase 2 target

- Program: [Enzyme Blue](https://immunefi.com/bug-bounty/enzymefinance/scope/#impacts)
- Target: `UnpermissionedActionsWrapper`
- Hunt note: [targets/enzyme-blue.md](targets/enzyme-blue.md)

That is the first real-world reproduction target because it has a clear authorization boundary and a reviewer-friendly proof-of-concept path.
