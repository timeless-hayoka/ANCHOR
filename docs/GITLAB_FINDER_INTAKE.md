# GitLab Finder: passive intake

**Status:** Read-only candidate discovery adapter. This is intentionally *not* a source-verification, eligibility, scope, or Trinity promotion system.

The ANCHOR GitHub Finder currently uses GitHub-only APIs and repository identities. Do **not** feed arbitrary GitLab URLs into a GitHub-only `owner/repository` scope check: the names may look identical despite different hosts and owners.

## How it works

1. Retrieve a **public** GitLab project search via the connected GitLab application (`list_projects`), retaining the provider-native JSON response with a `data` list. Do not include private GitLab account output in public repo artifacts.
2. Save only an explicitly reviewed, public-only JSON export to a temporary local file.
3. Run the adapter:

```bash
python scripts/gitlab_finder_intake.py \
  --input /tmp/gitlab-public-projects.json \
  --output /tmp/gitlab-intake.json
```

4. Review candidate ownership, code, current bounty program, chain/deployed asset, exact Git commit, and program limitations separately before any further handoff.

The adapter rejects non-public, archived, empty, duplicate, spoofed-host and inconsistent-identity entries. It refuses to mark a mere project search as a completed source scan and always emits `scan_status: metadata_only`, `scope_status: UNCONFIRMED`, `authorization: NOT_GRANTED`, and `trinity_state: NOT_CREATED`.

The output includes a SHA-256 of the input export to support audit review. It deliberately does not assign bounty eligibility, rank economic opportunities, issue scope grants, create Trinity findings, or perform external code execution. Outputs are new-file only and cannot overwrite an existing evidence report.

## Verified connection, 2026-11-03

The connected GitLab integration can list the user's projects and search GitLab's public projects. Its visible private DRIFT project is currently an **empty repository** from a failed GitHub import; it is **not** a working GitLab mirror of DRIFT. The existing GitHub repository remains authoritative for engineering. The public project search included numerous learning/example repositories; **none were verified as bounty-eligible**.

## Next integration

A later, separately reviewed provider-aware Finder collector can enrich the passive metadata with an immutable GitLab commit SHA and repository content. Keep the host as an explicit component in scope identity, and require independent program scope verification before invoking any non-passive test. Do not conflate GitLab project presence with permission for active security testing.
