# Recovery and validation plan — October 2026

This plan is intended for a phone-first maintainer without access to their former computers. It documents **unexecuted** checks; do not treat these commands as successful test results.

## Priority 0: preserve and secure

- Preserve the default branch; use pull requests for changes.
- Review repository collaborators, tokens, SSH keys, deploy keys, secrets, and Actions permissions from GitHub's mobile web interface.
- Rotate any credentials previously stored on unavailable devices or exposed in logs.
- Do not commit .env files, API keys, private keys, or bounty reports.

## Priority 1: clean-room baseline

On a temporary hosted development environment with Python 3.11+, create a clean clone:

```bash
git clone https://github.com/timeless-hayoka/ANCHOR.git
cd ANCHOR
python3 --version
./anchor env init
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q
./anchor knowledge list
./anchor benchmark latest
./anchor benchmark trends
./anchor strategy
```

Record Python version, installed dependency versions, test counts, exit codes, and errors. Missing published benchmark artifacts should be recorded as BLOCKED, not PASS.

## Priority 2: isolated benchmark

Install Foundry and reproduce the benchmark using an isolated educational contract corpus. See `docs/REPRODUCTION.md`. Never run exploits against live contracts or out-of-scope targets. Record true positives, false positives, false negatives, and reproduction success.

## Priority 3: integration

- ANCHOR -> AI-Forge-Protocol: validate command/API contracts and ensure failed validation cannot promote evidence.
- ANCHOR -> infj-bot DRIFT: verify ANCHOR_ROOT configuration, knowledge retrieval, memory persistence, and fail-closed behavior.
- Compare non-main branches before merging; check schema and evidence integrity.
- Freeze tested dependency versions only after baseline tests pass.

## Evidence log

For each check record: command, commit SHA, environment, timestamp, PASS/FAIL/BLOCKED, error excerpt, and evidence artifact path.

## Release gate

No production-ready claim until clean-machine tests, known-vulnerable/known-patched benchmark comparisons, authorization gates, evidence signatures, and independent reproduction all pass.

## Project attribution

See [COFOUNDERS.md](COFOUNDERS.md). Keep personal matters out of engineering documentation.
