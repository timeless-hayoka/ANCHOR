# ANCHOR

Proof-gated smart-contract hunting for authorized security research.

AI says there may be a bug. ANCHOR asks for evidence.

ANCHOR is the flagship because it is the clearest story and the most finished artifact: a local-first proof gate for authorized smart-contract security research. It turns raw tool output into a reproducible case, refuses to promote claims without proof, and preserves the trail from signal to signed evidence.

## The gate

A claim only moves forward when the evidence holds.

- `seeded false claim` -> rejected with `REJECTED - INSUFFICIENT EVIDENCE`
- `FIXTURE CORPUS - REAL TOOL EXECUTION` -> reproducible specimen run
- `Phase 2` -> one public, already-disclosed vulnerability reproduced in an authorized lab or local fork

The point is simple:

- AI says there may be a bug.
- ANCHOR asks for evidence.
- Bad claim fails the gate.
- Real claim reproduces.
- The proof is signed and preserved.

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

That is the first real-world reproduction target because it has the clearest authorization boundary and the most likely reviewer-friendly PoC path.
