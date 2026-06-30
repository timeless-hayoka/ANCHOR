# ANCHOR v1.0.0 Release Checklist

Release target: **v1.0.0**  
Baseline commit: `7125172` (main) + release-gate fixes  
Release date: **2026-06-30**

This checklist is the formal gate for ANCHOR’s first public framework release. Puppet V3 / mainnet-fork DVD coverage is **benchmark-environment work** and does **not** block v1.0.

---

## 1. Release gate (tests)

| Item | Status | Evidence |
|------|--------|----------|
| `mcp` dependency installed | **PASS** | `requirements.txt` includes `mcp>=1.27.0`; `.venv/bin/pip install -r requirements.txt` |
| `test_anchor_codex_mcp_print_config_matches_launcher` | **PASS** | Uses venv Python (matches `./anchor` wrapper) |
| Core release gate (102 tests) | **PASS** | `pytest tests/test_outcome_evidence.py tests/test_anchor_server.py tests/test_anchor_cli.py tests/test_anchor_sarif.py tests/test_codex_mcp_server.py tests/test_codex_mcp_launcher.py` |
| Full suite | **PASS** | `pytest -q` → 190 passed, 1 skipped |
| Core modules compile | **PASS** | `py_compile outcome_evidence.py anchor_server.py anchor_cli.py evidence_schema.py` |

### Gate fixes in this release

- `tests/test_anchor_cli.py` — codex MCP `--print-config` parity with launcher via venv Python
- `tests/test_ethernaut_source_comparison_benchmark.py` — SARIF suppression expectations (coin-flip noise → TN)

---

## 2. Reproducibility (`docs/REPRODUCTION.md`)

Quick path after clone + env init:

```bash
export ANCHOR_DVD_ROOT=/path/to/damn-vulnerable-defi
./anchor benchmark dvd phase1
./anchor benchmark latest
./anchor benchmark trends
./anchor strategy
```

| Item | Status | Evidence |
|------|--------|----------|
| `./anchor benchmark dvd phase1` produces run dir | **PASS** | `benchmarks/damn-vulnerable-defi/runs/<timestamp>/` with `benchmark.json`, per-challenge logs, detector stage |
| `./anchor benchmark latest` | **PASS** | Points to published DVD Phase 1 run |
| `./anchor benchmark trends` | **PASS** | Reproduction rate trend across published Phase 1 runs |
| `./anchor strategy` | **PASS** | Evidence-driven recommendation from trends + ledger |
| Manifest development entry on local rerun | **PASS** | New runs land as `development` until `./anchor benchmark publish` |

---

## 3. Published benchmark metadata

| Item | Status | Evidence |
|------|--------|----------|
| Current DVD Phase 1 published run | **PASS** | `dvd-phase1-local-2026-06-27T16-06-54Z` in `benchmarks/index.json` |
| Artifact path resolves | **PASS** | `benchmarks/damn-vulnerable-defi/runs/2026-06-27T16-06-54Z/benchmark.json` |
| Published record | **PASS** | `…/PUBLISHED.md`, `…/README.md` |
| Results summary | **PASS** | 16 passed / 2 failed / 0 timed out |
| Fork-dependent failures documented | **PASS** | See [Environmental limitations](#environmental-limitations-not-release-blockers) |

### Environmental limitations (not release blockers)

Two DVD Phase 1 challenges require a mainnet fork RPC (`MAINNET_FORKING_URL`). They are labeled `environment_dependent` in `challenge_expectations.json` and recorded as `environment_sensitive` in published run READMEs:

| Challenge | Expected outcome | Without fork RPC |
|-----------|------------------|------------------|
| `curvy-puppet` | `environment_dependent` | Forge test **FAIL** (documented in run log) |
| `puppet-v3` | `environment_dependent` | Forge test **FAIL** (documented in run log) |

These are **environment coverage gaps**, not proof-gate regressions. Resolving them is post-v1.0 benchmark work (do not delay the framework release).

---

## 4. Product spine verification

| Capability | Status |
|------------|--------|
| Unified evidence schema (`evidence_schema.py`) | **PASS** |
| Outcome insights + dashboard summary (`outcome_evidence.py`) | **PASS** |
| `/api/anchor/snapshot` → `evidence_summary` | **PASS** |
| Demo dashboard Evidence Sources / Latest Evidence panel | **PASS** |
| `APP_VERSION = "1.0.0"` in `anchor_server.py` | **PASS** |
| DVD Phase 1 (18 challenges + Slither stage) | **PASS** |
| `./anchor` CLI surface | **PASS** |

---

## 5. Tag and publish

```bash
cd ANCHOR
git tag -a v1.0.0 -m "ANCHOR v1.0.0 — proof-gated smart contract hunting"
git push origin main v1.0.0
gh release create v1.0.0 --title "ANCHOR v1.0.0" --notes-file docs/V1_RELEASE_CHECKLIST.md
```

| Item | Status |
|------|--------|
| Release-gate commit on `main` | See git log after merge |
| Annotated tag `v1.0.0` | Pending / completed at release time |
| GitHub Release | Pending / completed at release time |

---

## Release notes — ANCHOR v1.0.0

### Proof-gated promotion model

ANCHOR separates **signals** from **findings**. A claim advances only through a falsifiable path:

`signal → hypothesis → repro_attempted → reproduced_real → council_accepted → report_ready`

Scanners and AI may suggest; ANCHOR promotes only when reproduction and review evidence exist. Failed attempts are retained as data.

### Immutable evidence chain

- Canonical `EvidenceRecord` schema with signed bundle support
- Benchmark and hunt archives emit structured evidence at creation time
- Outcome ledger (`outcomes/ledger.jsonl`) links real-world results to artifact paths
- Dashboard and CLI render the same `evidence_summary` (Benchmarks, BugBot Training, Hunt Analysis)

### DVD Phase 1 results (published)

**Run:** `dvd-phase1-local-2026-06-27T16-06-54Z`

- **16 / 18** challenges pass locally with Slither detector stage
- **2 / 18** fail without mainnet fork RPC (`curvy-puppet`, `puppet-v3`) — expected, documented
- Regression report, detector provenance, and per-challenge comparison state in run artifacts

### Benchmark and dashboard visibility

- `./anchor benchmark {latest,history,trends,compare,publish}`
- `./anchor strategy` — single trend source (`anchor_trends.py`)
- Local server: demo UI + SSE hunts + snapshot API
- Codex MCP server for workspace-aware operator snapshots

### Known fork-RPC limitation

Set `MAINNET_FORKING_URL` to a valid Ethereum mainnet RPC endpoint to reproduce fork-dependent DVD challenges. Without it, Phase 1 correctly reports **89% local reproduction rate** with explicit `environment_sensitive` labels — not a hidden failure.

### Post-v1.0 first capability track

**A-001 — SARIF pipeline benchmarking** (`docs/ANCHOR_WORK_QUEUE.md`)

Measure TP/FP/FN against `benchmarks/sarif-known-findings/` corpus through the normal CLI path. This is signal-quality measurement, not a release blocker.

---

## Sign-off

- [x] Release gate green
- [x] Reproduction spine verified
- [x] Published DVD Phase 1 metadata validated
- [x] Fork failures documented as environmental
- [x] Release notes complete
- [ ] Tag `v1.0.0` pushed
- [ ] GitHub Release published
