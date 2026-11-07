# ANCHOR local run server

This is a local, single-user orchestration and evidence-display service. It does
not independently validate exploit impact and has no interactive model or login
session. Keep it bound to loopback. The public website is a static demo.

## Install and start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn anchor_server:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/health
```

`/` redirects to the static demo. `/api/service` returns version and public-key
metadata. A locally persisted Ed25519 key signs content; a signature attests to
bytes, **not to the truth of a vulnerability claim**. Signed wrappers explicitly
say `CONTENT_SIGNATURE_ONLY`.

## Supported behavior

| Capability | Current behavior |
| --- | --- |
| Explicit demo | POST `/runs` with `{"mode":"demo"}`. Fixtures/events carry `DEMO_FIXTURE` provenance; no engines execute. |
| Hunt orchestration | Requires an existing, explicitly approved local Python helper and a fresh run-bound output or authenticated telemetry. No general default hunt driver is bundled. |
| Registry import | Preserves unverified claims. Does not invent tool executions, successful assertions, or verified artifacts. |
| Live proof label | Imported/producer `REPRODUCED_REAL`, `COUNCIL_ACCEPTED`, and `REPORT_READY` claims become `POC_EXECUTED_UNPROVEN`. Independent proof promotion is not wired to this server. |
| Accuracy | Precision/recall/F1 are null for live runs without labeled ground truth. Demo scores remain illustrative. |
| Trinity chat | Help-only response with `model_connected=false`. It does not invoke a model. |
| Server state | In-memory runs, cases and event replay. Restart loses this state. |
| Generic target analysis | Still incomplete. File inspection/skipped tests return partial analysis, not a clean scan. |

Missing/invalid modes and malformed inputs are rejected. Case lookup never
creates a specimen result for a case that has not run.

## Trusted helper execution

Set `ANCHOR_PROJECT_ROOT` to the approved helper project. Script paths must
resolve beneath it and match the canonical paths in `scripts/registry.json` or
`ANCHOR_ALLOWED_HUNT_SCRIPTS`. The latter defaults to the two historical names
`trinity_hunt_v4_2_fixed.py,anchor_hunt.py`, neither of which is bundled.
A matching basename in another directory is not authorized. Explicit script
arguments require `ANCHOR_ALLOW_HUNT_ARGS=1`; do not enable it for untrusted
helpers. Configured helpers are trusted operator code, not arbitrary uploaded
contract code.

Hunts have a 120-second wall/CPU limit, 2 GiB address-space limit, 1 MiB output
and registry limits, and process-group termination on failure/cancellation.
Only a small environment allowlist plus run-specific variables is inherited.
These limits are **not** filesystem/network isolation for trusted helpers.

For target Forge execution through BugBot, bubblewrap is required and applies
separate filesystem/network namespaces with no host home directory and no
network. Target files are mounted at `/work`; system libraries are read-only.
FFI is disabled via the execution environment. Tools and compiler prerequisites
must be available within that sandbox. Missing tools, namespace failures or
compiler failures do not fall back to unsandboxed execution. Only Linux/POSIX
bounded execution is currently supported.

## Producer and registry protocol

The server launches a helper with:

- `ANCHOR_SERVER_URL`, `ANCHOR_RUN_ID`, `ANCHOR_TARGET`
- `ANCHOR_REGISTRY_PATH`: fresh `.anchor/runs/<run_id>/registry.json` by default
- `ANCHOR_INGEST_TOKEN`: per-run secret; never log or archive it

Use `anchor_emit` from a server-launched helper. It sends
`X-Anchor-Ingest-Token` automatically. Standalone `start_run()` is explicitly
unsupported, and producers cannot complete/cancel a run through telemetry.
The server owns lifecycle and waits for the subprocess result.

A helper writing a registry must use an object with `run_id` equal to
`ANCHOR_RUN_ID`, `target` equal to `ANCHOR_TARGET` (or null if unset), and
`results` containing case objects with unique string IDs. Existing output paths,
symlinks, malformed/unbound records, no output, or nonzero exit reject the run.
Bindings prevent accidental replay; they do not authenticate contract source
or prove impact. Raw claimed labels/artifacts remain explicitly unverified.

Producer event types: `case.started`, `stage.started`, `finding.detected`,
`finding.correlated`, `poc.result`, `case.completed`, `log.line`.
`poc.result.exploit_verified` must be a JSON boolean; even true is not proof.
`run.completed`, `run.failed`, and `run.stopped` are terminal server events.
Terminal runs reject further ingest with HTTP 409. Clients must handle all
three terminal events. The service caps runs at 100 and nonterminal events per
run at 10,000; restart the local service when run capacity is reached.

## Browser boundary

`ANCHOR_CORS_ORIGINS` is a comma-separated list of explicit trusted origins;
defaults are `http://localhost:8000,http://127.0.0.1:8000`. Wildcard origins are
rejected. Mutating requests with other browser origins are rejected before
routing, including simple requests that do not trigger CORS preflight.
Mutating request bodies are capped at 1 MiB, including chunked bodies.
Non-browser local requests without an Origin header are allowed. Producer
telemetry additionally requires its per-run token. This is not authentication
for remote/multi-user deployment. No cookie/login protection is implemented.

## Routes

| Route | Purpose |
| --- | --- |
| GET `/api/health`, `/api/service`, `/pubkey` | Health, version and public-key metadata |
| POST `/runs` | Explicit demo or configured hunt |
| GET `/runs/{id}/events?after={event_id}` | SSE replay and streaming |
| POST `/runs/{id}/ingest` | Authenticated producer telemetry |
| POST `/runs/{id}/cancel` | Cancel and kill helper process group |
| GET `/runs/{id}/registry` | Current/final normalized registry |
| GET `/cases/{id}` | Existing case; no fixture fallback |
| POST `/evidence/sign` | Content signature, not proof attestation |
| GET `/api/anchor/snapshot`, `/api/knowledge` | Repository evidence summaries and knowledge |
| POST `/api/trinity/chat` | Explicit help-only endpoint |

Run `python -m pytest tests/ -q` for regressions. The bundled SARIF corpus checks
processing; separate DVD CI checks existing lab proofs. Neither establishes
fresh general-target detection through this server. Engine integration,
production-matched reproduction, dependency locking, and full server extraction
remain separate work.
