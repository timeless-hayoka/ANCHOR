---
schema_version: 1.0
target_id: dvd-local-lab
target_ref: abc123def4567890abcdef1234567890abcdef12
scope_policy_url: https://example.com/security/scope
permitted_actions:
  - analysis
prohibited_actions:
  - mainnet-exploit
disclosure_channel: local-lab-only
reviewer_decision: authorized
reviewed_at: 2026-06-30T12:00:00+00:00
identity_status: local_fixture_unpinned
expires_at: 2027-06-30T12:00:00+00:00
evidence_url: https://example.com/evidence/dvd-local-lab
evidence_path: tests/fixtures/scope_evidence.md
---

# Scope confirmation (test fixture)

Authorized local lab target for unit tests only.
