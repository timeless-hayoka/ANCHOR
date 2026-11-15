# HackerOne read-only importer: security review (draft)

## Scope and provenance

This increment adds `hackerone_readonly.py` and offline tests only. It does not modify ANCHOR's proof gate, Trinity state machine, or execution entry points. Official HackerOne Hacker API documentation: https://api.hackerone.com/getting-started-hacker-api/ and https://api.hackerone.com/hacker-resources/.

Supported read operations: `GET /v1/hackers/programs`, `GET /v1/hackers/programs/{handle}`, `GET /v1/hackers/programs/{handle}/structured_scopes`, `GET /v1/hackers/programs/{handle}/scope_exclusions`. The importer deliberately does not accept arbitrary URLs, HTTP methods, or caller-supplied hosts. It disables HTTP redirects and limits response bytes and request duration. Credentials are sourced from `HACKERONE_USERNAME` and `HACKERONE_API_TOKEN` environment variables (or explicit constructor parameters for tests).

## Trust boundary

Program discovery is **not** authorization. `programs()` maps each valid program into `DiscoveredTarget` with `AuthorizationStatus.SCOPE_UNVERIFIED`, no verified timestamp, no in-scope assets and no authorization evidence. A separate, independently reviewed scope-verification process must authorize targets before any active testing. This adapter never imports a program into Trinity, changes a lead state, submits a report or performs a scan.

## Security properties and limitations

- Credentials are not printed, stored or returned. HTTP error bodies and exception strings are discarded. Failures use sanitized messages.
- An explicit path allowlist and strict handle grammar block arbitrary endpoint access, query injection and path traversal.
- Redirects are rejected; the only outbound request origin is `https://api.hackerone.com`.
- 401/403, 429, timeouts, connection failures, invalid JSON and malformed program records fail closed.
- Only the first programs page is imported. Pagination, scope interpretation, retry/backoff, response-schema expansion and authenticated live smoke tests are **out of scope** for this first increment.
- HackerOne program policy and scope may change; even valid API data must not be treated as authorization without review.
- GitHub Actions secrets are not available automatically to ChatGPT; do not expose these secrets to untrusted pull-request jobs.

## Validation

Run offline from the ANCHOR repository root:

```bash
python -m unittest discover -s tests -p 'test_hackerone_readonly.py' -v
```

Local isolated validation against a minimal stand-in of `bounty_scout` passed eight tests. This is **not** proof that ANCHOR's complete repository tests pass. CI and review against the actual repository remain required before merging.

## Review checklist

- [ ] Run focused tests in ANCHOR CI against real `bounty_scout.py`
- [ ] Run the repository's existing full test suite and inspect regressions
- [ ] Review network redirection and exception-handling edge cases
- [ ] Review handling of private program metadata before enabling logs/artifact persistence
- [ ] Verify live authentication only from an explicitly approved trusted environment, with secrets masked
- [ ] Keep PR draft until all gates pass
