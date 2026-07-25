Repo: fluxion-protocol/fluxion-contracts

Why it is interesting: Production-ready smart contracts for continuous asset streaming on Stellar Soroban. Implements real-time payroll, token vesting with cliffs, and grant distribution. Audit-ready with 100+ tests, comprehensive documentation, and enterprise-class security. Apache 2.0 licensed.
Authorization state: Explicitly authorized bounty / audit scope
Suggested posture: Local clone analysis allowed and scope-limited review is encouraged
Priority score: 100/100
Review state: Explicitly authorized bounty / audit scope
Repo URL: https://github.com/fluxion-protocol/fluxion-contracts

Likely surface:
- smart-contract logic
- upgradeability
- external calls
- tests / fuzzing / CI

Existing security signals:
- SECURITY.md absent
- CodeQL absent
- Semgrep absent
- Slither absent
- tests/fuzzing present
- dependency manifests absent
- audit/advisory language present
- release cadence: inactive

Dependency manifests:
- none detected

Release cadence: inactive

Why it is interesting:
repo is not archived

Recommended next action:
- Read contribution and security policy
- Check bounty/scope
- Run local static analysis only if authorized or clearly permitted

Possible issue angles:
- testing/invariants
- docs/workflow clarity
- regression harness or machine-readable output
