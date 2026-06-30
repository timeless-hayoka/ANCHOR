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

> Protected analysis execution complete for local workspaces; GitHub selected-repo flow and per-target fuzz profiles pending.

- [x] `require_authorized_scope(...)` with canonical `ANALYSIS = "analysis"`
- [x] `ScopeGrant` derived from validated `scope_confirmation.md` / JSON (not self-granted)
- [x] `anchor bugbot scope-check --confirmation …` writes atomic active grant
- [x] Protected analysis body: clone → inspect → test → fuzz (test/fuzz skip gracefully)
- [ ] GitHub selected-repo flow wiring
- [ ] Per-target fuzz profiles and analysis archival

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
