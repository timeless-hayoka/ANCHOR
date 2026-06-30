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

**BugBot / GitHub selected-repo workflow status:**

> Fail-closed authorization primitive and evidence-backed scope-check writer complete; protected analysis execution pending.

- [x] `require_authorized_scope(...)` with canonical `ANALYSIS = "analysis"`
- [x] `ScopeGrant` derived from validated `scope_confirmation.md` / JSON (not self-granted)
- [x] `anchor bugbot scope-check --confirmation …` writes atomic active grant
- [x] `anchor bugbot analyze` gated entrypoint (no target-code activity yet)
- [ ] Analysis execution (clone, inspect, test, fuzz) below the gate

## P0.5 — BugBot hunt pipeline (paused)

Workflow: `crawl → select → plan → scope-check → analysis`

- [x] Scope grant producer (`scope-check`) from documented evidence
- [x] Protected analysis entrypoint stub (`bugbot analyze`)
- [ ] `crawl`, `select`, `plan` commands (planning-only)
- [ ] GitHub selected-repo flow wiring
- [ ] Target-code analysis implementation below the gate

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
