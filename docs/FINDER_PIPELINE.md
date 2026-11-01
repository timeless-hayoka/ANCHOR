# Finder pipeline

Finder discovers and ranks public repositories. Ranking is research priority, not proof of a vulnerability or permission to test. Discovery never grants analysis authorization, regardless of README keywords or score.

## Run the workflow

From the ANCHOR checkout, install `requirements.txt` and set `GITHUB_TOKEN` (or authenticate `gh`) for GitHub API quota. Never put tokens in commands committed to the repository.

```bash
./anchor github crawl --query 'solidity foundry invariant' --limit 5 --per-query 5
./anchor github select owner/repository --run-id RUN_ID
./anchor github plan owner/repository --run-id RUN_ID
./anchor github scope-check owner/repository --run-id RUN_ID --json
```

`crawl-auth`, `crawl-upgrade`, `crawl-accounting`, `crawl-oracle`, and `crawl-external` use the same pipeline with different ranking profiles. `--output-root` can isolate a campaign; use the same root and run ID throughout.

The discovery run contains `bundle.json`, `summary.md`, and per-repository briefs. Selection copies a candidate into `selected/` without changing the source bundle. Planning writes `hunt_plan.json`, `hunt_plan.md`, and an initially unapproved `scope_confirmation.md`. Planning does not execute analysis or a proof harness.

## Scan outcomes and exit codes

Every candidate has `scan_status` and `scan_errors`:

- `complete`: requested enrichment completed, including directory, workflow and release metadata.
- `metadata_only`: enrichment was deliberately disabled with `--no-readmes`.
- `incomplete`: an API, quota, transport or response-shape failure prevented enrichment. The error is preserved; unavailable information is not labeled absent.

An expected 404 for an optional directory or README means it was not found. Rate limits, timeouts, permissions and malformed payloads are errors rather than evidence of absence. A complete scan describes successful retrieval, not complete security coverage.

Crawl exits **0** on completed retrieval, **2** when a bundle was saved with incomplete enrichment, and **1** when the command fails. Scope-check exits **0** only when authorized, otherwise **1**. Scheduled discovery uploads its artifacts even after a nonzero exit. A zero-result search is a completed search, not a finding.

## Fill the scope record

Review the actual policy and preserve a local evidence snapshot. Fill the generated Markdown frontmatter with:

- `schema_version: 1.0`
- `target_id`: exact `owner/repository` from the selection
- `target_repo_url`: exact `https://github.com/owner/repository`
- `target_ref`: approved commit, tag or release; use a commit SHA for immutable runs
- `scope_policy_url`, `evidence_url`: source HTTP(S) URLs
- `evidence_path`: existing local evidence file, absolute or relative to the ANCHOR checkout
- `permitted_actions`: list containing `analysis` when the policy permits it
- `prohibited_actions`, `disclosure_channel`: actual policy boundaries and reporting channel
- `reviewer_decision: authorized` only after review
- `reviewed_at`: timezone-aware ISO timestamp; optional `expires_at` limits validity

The identity defaults to `verified_repo`; a local fixture identity cannot authorize a selected GitHub repository. Empty templates, example options, duplicate decisions, missing evidence, mismatched identities, missing revisions, future review dates, expired grants and grants without analysis permission remain blocked. Existing free-form records must migrate to this structured format; a bare `reviewer_decision: authorized` is insufficient.

Finder validates the record using BugBot's scope evidence parser and request validator. It does not issue an operational grant automatically. After a successful Finder scope check, pass that same file to the operational gate:

```bash
./anchor bugbot scope-check --confirmation discoveries/github/RUN_ID/selected/owner-repository/scope_confirmation.md
./anchor bugbot analyze --target-id owner/repository --target-ref APPROVED_REF
```

The analysis command must match the grant's target and revision. Scope approval enables only recorded actions; reproduction, impact review and finding promotion are later stages.

## Scout / Sentinel path

Sentinel's reachability score also cannot authorize a target. Operator-reviewed confirmations can be supplied separately from discovery data:

```bash
python bounty_sentinel.py discoveries/scout/RUN.jsonl --confirmation-dir scope/confirmations
```

Name each record `<slugged-target-id>.md` (lowercase, non-alphanumeric runs replaced by `-`). The scope record must match that target ID and repository and permit analysis. Discovery JSON cannot nominate its own confirmation file. Without a valid record, targets stay unapproved. Verification expiry cannot outlive the scope record.

## Verification

```bash
python -m pytest tests/test_github_discovery.py tests/test_finder_pipeline.py tests/test_bounty_sentinel_validation.py -q
python -m pytest tests/ -q
```

The fixture integration covers GitHub-shaped HTTP decoding → bundle → selection → plan → blocked default scope → reviewed scope → operational grant. Negative cases cover quota errors, missing files, score-based authorization, identity mismatches, expiry and denied actions. Tests use synthetic policies and do not authorize real targets.
