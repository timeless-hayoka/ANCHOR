Repo: omniologynow-rgb/omniology-contract

Why it is interesting: Omniology's Solana smart contract — Anchor Rust source, tests, and security documentation. AI agent contest platform on Solana mainnet.
Authorization state: Explicitly authorized bounty / audit scope
Suggested posture: Local clone analysis allowed and scope-limited review is encouraged
Priority score: 100/100
Review state: Explicitly authorized bounty / audit scope
Repo URL: https://github.com/omniologynow-rgb/omniology-contract

Likely surface:
- smart-contract logic
- upgradeability
- access control
- external calls
- parsing / serialization

Existing security signals:
- SECURITY.md absent
- CodeQL absent
- Semgrep absent
- Slither absent
- tests/fuzzing not obvious
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
