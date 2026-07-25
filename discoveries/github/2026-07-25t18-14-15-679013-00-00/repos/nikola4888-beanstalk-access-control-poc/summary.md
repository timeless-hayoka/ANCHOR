Repo: nikola4888/beanstalk-access-control-poc

Why it is interesting: Proof of Concept demonstrating zero-address admin vulnerability in BeanstalkERC20 smart contract for Immunefi bug bounty.
Authorization state: Public repo / no confirmed bounty scope
Suggested posture: Passive review only until scope is confirmed
Priority score: 70/100
Review state: Passive-only
Repo URL: https://github.com/nikola4888/beanstalk-access-control-poc

Likely surface:
- unknown

Existing security signals:
- SECURITY.md absent
- CodeQL absent
- Semgrep absent
- Slither absent
- tests/fuzzing not obvious
- dependency manifests absent
- no audit/advisory language found
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
- authorization boundary review
- permission gate review
- role and owner path review
