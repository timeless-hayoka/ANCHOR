# Prioritized Development Backlog

Ordered for evidence-first ANCHOR evolution. Revisit after each published benchmark tier.

## P0 — Foundation (now)

- [x] Structured `knowledge/` corpus + `KnowledgeProvider`
- [x] CLI `anchor knowledge {list,show,search,refs}`
- [x] HTTP knowledge endpoints on `anchor_server`
- [x] Wire Trinity/Drift MCP tools (`anchor_knowledge_*`) to call `KnowledgeProvider`
- [x] `knowledge/pipeline.py` archival sidecar (training / detectors / scenarios)
- [x] `bugbot/trainer.py` — non-fatal archive after training run
- [x] `anchor bugbot train --scenario …` operator surface
- [x] `require_authorized_scope(...)` gate in `bugbot/scope.py` (default: planning only)

**BugBot / GitHub selected-repo workflow status (checkpoint `25bab55`):**

> Planning and fail-closed authorization primitive complete; scope-confirmation writer and protected analysis entrypoint pending.

What this means:

- The gate lives in `bugbot/scope.py` and is **not** wired into ANCHOR’s GitHub selected-repo flow yet.
- It protects **future** BugBot analysis commands (`require_authorized_scope` as line 1).
- It does **not yet prove** the full path enforces `crawl → select → plan → scope-check → analysis`.
- Safe default today: **no grant exists → deny analysis** (planning only).

Resume order when un-paused:

1. **scope-check / scope grant** — writes verifiable authorization record; binds `target_id` + permitted actions
2. **`require_authorized_scope` validates** that record
3. **`cmd_bugbot_analyze(...)`** — only after the gate: clone, inspect, test, fuzz, or analyze

## P0.5 — BugBot hunt pipeline (paused)

Workflow: `crawl → select → plan → scope-check → analysis`

- [ ] Scope grant / scope-check command (authorization record writer)
- [ ] `current_scope_state()` reads and validates grant records
- [ ] Protected analysis entrypoint (`cmd_bugbot_analyze` + gate as first line)
- [ ] Wire gate into any other target-touching commands as they ship
- [ ] `crawl`, `select`, `plan` remain planning-only until scope-check passes

## P1 — Graph & timeline
- [ ] Timeline view: signal → cluster → repro → outcome per case_id
- [ ] Dashboard panel for graph subset (filter by cluster_id)

## P2 — Retrieval quality

- [ ] Optional Chroma index over `knowledge/` (separate from vault corpus)
- [ ] Tag-aware search (`subsystem:sarif confidence`)
- [ ] Version stamp in manifest when topics change materially

## P3 — Cloud optional paths

- [ ] Published-tier sync to object storage (opt-in env)
- [ ] Remote read-only dashboard for signed bundles only
- [ ] LLM cluster summaries behind explicit `--llm` + cost guard

## P4 — Research loop depth

- [ ] Auto-rank hunts from `research_loop` + outcome insights merge
- [ ] DefiHackLabs source-comparison benchmark in default CI gate
- [ ] Economic context tuning from ledger feedback loop

## Design philosophy for future features

1. **Prove before promote** — every feature must declare which gate it respects.
2. **Append-only history** — ledger and benchmark manifest stay auditable.
3. **Retrieve modular docs** — grow `knowledge/` before adding prompt surface area.
4. **Benchmarks as contracts** — new pipeline stages ship with a corpus regression first.
