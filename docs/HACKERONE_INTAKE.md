# HackerOne Scope Intake

ANCHOR can collect a read-only snapshot of a HackerOne program's current policy,
structured scopes, and scope exclusions. The snapshot is evidence for human scope
review; it does not authorize automated testing by itself.

## Repository secrets

Configure these GitHub Actions secrets:

- `HACKERONE_USERNAME`: the HackerOne researcher username (not an email address)
- `HACKERONE_API_TOKEN`: the HackerOne researcher API token

Do not use a GitHub personal access token for either value. The workflow never
writes these credentials to its artifact.

## Run the intake

1. Open **Actions → HackerOne scope intake → Run workflow**.
2. Enter the program handle from `https://hackerone.com/<handle>`.
3. Download the `hackerone-scope-<handle>` artifact after the run completes.
4. Review the policy, every candidate asset's instructions, and all exclusions
   before creating an active scope grant or testing anything.

Artifacts expire after seven days. The workflow does not submit reports, modify
HackerOne data, probe program assets, or schedule recurring runs.

## Crawl accessible programs

Run **Actions → HackerOne scope crawler → Run workflow** to enumerate programs
visible to the researcher account. By default, the crawler selects only programs
that are open for submissions and explicitly offer bounties. Programs with Gold
Standard Safe Harbor and open scopes are ranked first, and each run is capped at
the requested number of programs (maximum 100).

The artifact contains a `crawl-index.json` manifest and one scope snapshot per
successfully fetched program. A failure for one program is recorded in the index
without discarding other snapshots. Check **Include VDP** only when you also want
non-bounty vulnerability disclosure programs.

The crawler is intentionally manual until its first artifact has been reviewed.
It performs HackerOne API reads only; it does not connect to any scoped asset.

For a local read-only run, set both credentials in the environment and execute:

```bash
python hackerone_intake.py --program-handle <handle>
```

To crawl up to 25 open bounty programs locally:

```bash
python hackerone_intake.py --crawl --limit 25
```

## Review scope and select methods

An API snapshot is evidence, not execution authorization. Generate a fail-closed
review worksheet from one downloaded snapshot:

```bash
python hackerone_methodology.py prepare-review \
  --snapshot discoveries/hackerone/<handle>-scope.json \
  --output discoveries/hackerone/<handle>-review.json
```

The reviewer must read the current program policy and exclusions, then complete:

- `decision`, `reviewer`, `reviewed_at`, and `expires_at`
- `policy_confirmed` and `exclusions_confirmed`
- a positive `rate_limit_per_minute`
- each scope's `decision` and `system_kinds`
- `permitted_methods` and any additional `prohibited_methods`
- the separate active and state-changing approval gates

Reviews expire after at most seven days and are cryptographically tied to the
exact scope snapshot. If the snapshot changes, the review must be repeated.

Compile the completed worksheet into a method plan:

```bash
python hackerone_methodology.py compile-plan \
  --snapshot discoveries/hackerone/<handle>-scope.json \
  --review discoveries/hackerone/<handle>-review.json \
  --output discoveries/hackerone/<handle>-hunt-plan.json
```

The compiler rejects unknown or contradictory methods, ineligible assets,
expired reviews, and changed snapshots. High-impact methods such as denial of
service, mass scanning, social engineering, credential stuffing, destructive
testing, accessing other users' data, and moving production funds are always
blocked.

The result remains `planning_only` and sets `execution_authorized` to `false`.
Before any target interaction, promote the reviewed evidence through ANCHOR's
existing active scope-grant process. Every later action must match that grant;
the hunt plan alone never authorizes testing.
