# Bug Hunting Crawler

This file defines the public, passive inputs ANCHOR should collect when building bug-hunting training material and hunt plans.

The goal is not to exploit anything automatically.
The goal is to gather useful evidence, rank likely bug surfaces, and turn that into reproducible hunting input.

## What the crawler should do

1. Collect public repository signals.
2. Extract bug-relevant patterns from code, docs, tests, workflows, and release history.
3. Rank repositories and targets by likely bug surface.
4. Emit a compact evidence bundle that can feed ANCHOR hunt planning.

## Best sources

Prioritize public data that can be checked without intrusive behavior:

- `README.md` and project docs
- `SECURITY.md` and contribution policy files
- CI workflows in `.github/workflows/`
- dependency manifests such as `foundry.toml`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`
- tests, fuzz harnesses, and invariant checks
- issue templates, release notes, changelogs, and audit references
- repo metadata such as stars, forks, language, update frequency, and archived status

## Useful bug-finding signals

The crawler should look for signals that commonly lead to real findings:

- authorization gates and role checks
- upgradeability and initializer paths
- external calls, callbacks, and delegatecall usage
- accounting, balance, share, and rounding logic
- stale oracle, pricing, and input validation paths
- serialization and parsing boundaries
- state machine transitions and queue processing
- retry, recovery, pause, and resume behavior
- dependency and integration risk
- missing or weak regression tests

## Tips that matter in practice

- Focus on the boundary, not the symptom. A bug is usually real when the wrong actor can reach the state-changing path.
- Look for the shortest path from public entrypoint to persistent state mutation.
- Compare intended state transitions against actual transitions.
- Treat repeated edge cases as more important than a single odd result.
- Prefer claims that can be falsified with one test or one fork reproduction.
- Separate noise from impact. A weird code path is not a bug unless it changes state, value, authority, or availability in a meaningful way.
- Recheck the same path under different conditions: empty state, full state, first call, second call, paused state, upgrade state, and recovery state.

## Bug classes worth ranking highly

- access control failure
- initialization / upgrade mistake
- reentrancy or unsafe callback flow
- accounting drift or rounding accumulation
- stale oracle acceptance
- unchecked return value or failed external call handling
- unsafe state transition
- replay or duplicate processing
- dependency or integration mismatch
- missing invariant coverage around a critical boundary

## What the crawler should record for each candidate

Each candidate should carry a small evidence bundle:

- repository full name
- target files or paths that triggered interest
- bug class or classes that match
- short reason for interest
- authorization posture
- likely surface
- dependency manifests present
- test and workflow signals
- evidence source URLs or file paths
- recommended next action

## Simple scoring model

Use a score that favors:

- explicit security language
- active development
- tests or fuzzing already present
- code that touches authority, state transitions, or external calls
- visible bug-bounty or audit context
- recent changes in sensitive files

Reduce score when:

- the repo is archived
- there is no obvious executable surface
- the repo is mostly documentation or scaffolding
- the candidate is only interesting because of vague wording

## Output format

The crawler output should be easy to consume by ANCHOR:

```json
{
  "repo": "owner/name",
  "score": 0,
  "authorization_state": "Public repo / no confirmed bounty scope",
  "likely_surface": ["access control", "external calls"],
  "signals": ["CodeQL present", "tests/fuzzing present"],
  "evidence_sources": [
    {"type": "api", "url": "https://api.github.com/repos/owner/name"},
    {"type": "file", "path": "README.md"}
  ],
  "next_action": "Review SECURITY.md and map the call path"
}
```

## Safe operating rules

- Use public metadata and public code only.
- Do not clone, scan, or fuzz automatically unless scope is confirmed.
- Do not open issues, PRs, or contact maintainers from the crawler.
- Keep raw evidence so the ranking can be reviewed later.
- Preserve the distinction between "interesting" and "authorized".

## Good starter queries

- `smart contract security fuzzing invariant testing`
- `solidity foundry echidna slither`
- `upgradeable proxy access control tests`
- `oracle stale price rounding accounting`
- `bug bounty security policy codeql semgrep`

## Bug-class crawlers

Use a crawler profile when you want the ranking to bias toward one class of bugs:

- `./anchor github crawl-auth`
- `./anchor github crawl-upgrade`
- `./anchor github crawl-accounting`
- `./anchor github crawl-oracle`
- `./anchor github crawl-external`

Each profile changes the default search queries and boosts repositories whose docs, workflows, and code signals match the target class.

## Relation to ANCHOR

This crawler is the front end of the hunt pipeline.

It feeds:

- `./anchor github crawl`
- `./anchor github select <repo>`
- `./anchor github plan <repo>`
- `./anchor hunt plan --target <note>`

The important boundary stays the same:

passive discovery first, human review second, scope confirmation before analysis, reproduction before promotion.
