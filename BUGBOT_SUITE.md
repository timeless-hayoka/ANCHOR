# BugBot Suite: Scout → Sentinel → Forge → Trinity

The complete bounty hunting pipeline. Discovers authorized targets, verifies scope, normalizes into hunt packages, and feeds Trinity for investigation.

```text
BugBot Scout ──────────→ BugBot Sentinel ──────→ Target Forge ────→ Trinity
Discovery              Scope Verification      Normalization      Investigation
(Immunefi,            (Official pages,         (Hunt packages,    (Structured
 Code4rena,            Repository links,        Environment       research,
 Sherlock)             Commit pinning)          specs)             Reproduction)
```

## Critical Principle

**Trinity should never ask "Am I allowed to hunt this?"**

The answer comes from BugBot with proof:

```python
if hunt_package.target.state != AuthorizationState.AUTHORIZED_ASSET_MATCHED:
    reject()
if not hunt_package.evidence:
    reject()
```

Only hunt packages with exact `AUTHORIZED_ASSET_MATCHED` state and evidence reach Trinity. All three layers enforce hard gates before forwarding.

## Pipeline Layers

### 1. Scout: Discovery

Finds programs on official bounty platforms.

```bash
python3 bounty_scout.py --platform immunefi
python3 bounty_scout.py --platform code4rena
python3 bounty_scout.py --all-platforms -v
```

**Output**: `discoveries/scout/scout_*.jsonl` (discovered targets)

**What Scout does:**
- Queries official bounty platform APIs
- Extracts program metadata and scope assets
- Normalizes to `DiscoveredTarget` format
- Marks as `authorization_status: SCOPE_UNVERIFIED`

**What Scout does NOT do:**
- Verify that scope is current
- Confirm repository links
- Test network access
- Make assumptions about authorization

### 2. Sentinel: Scope Verification

Confirms targets are actually authorized and scope is current.

```bash
python3 bounty_sentinel.py discoveries/scout/scout_immunefi_2026-07-24.jsonl
```

**Output**: 
- `discoveries/sentinel/verified_*.jsonl` (authorized targets)
- `discoveries/sentinel/rejected_*.jsonl` (failed targets)

**Hard gates:**
```python
# Gate 1: Platform URL must be accessible
if not platform_url_accessible():
    reject()

# Gate 2: Repository must be linked to official program
if not repository_linked():
    reject()

# Gate 3: Scope assets must be defined
if not in_scope_assets:
    reject()

# Gate 4: Confidence must be sufficient (≥0.7)
if verification_confidence < 0.7:
    reject()
```

**What Sentinel does:**
- Verifies platform URLs are accessible
- Confirms repository links match official programs
- Checks that scope assets are defined
- Computes confidence scores
- Records verification method and evidence

**What Sentinel does NOT do:**
- Perform security analysis
- Extract exploit paths
- Judge complexity or payout
- Make strategic decisions

### 3. Forge: Normalization

Converts verified targets into complete hunt packages.

```bash
python3 target_forge.py discoveries/sentinel/verified_2026-07-24.jsonl \
    --discovery-file discoveries/scout/scout_immunefi_2026-07-24.jsonl
```

**Output**: `discoveries/forge/hunt_packages_*.jsonl` (Trinity-ready packages)

**What each package contains:**

```json
{
  "hunt_id": "hunt_yearn_v3_001",
  "target": {
    "program": "Yearn Finance v3",
    "platform": "immunefi",
    "repository": "https://github.com/yearn/yearn-v3",
    "authorized": true,
    "authorization_method": "official_page",
    "verification_confidence": 0.85,
    "commit_sha": "7ff011a7ff5e69fb6ba0f2fa6e4ba4f1c0c9c1a0",
    "rpc_env_var": "ETHEREUM_RPC_URL"
  },
  "scope": {
    "in_scope": {
      "contract": [
        {
          "identifier": "0x4D7590eB56c3529d67dff690d1338D0c4E6B800C",
          "label": "Yearn Strategy Vault"
        }
      ]
    },
    "out_of_scope": {...},
    "forbidden_methods": ["calling-live-contracts", "submitting-exploits"],
    "kyc_required": false
  },
  "environment": {
    "framework": "foundry",
    "fork_required": true,
    "fork_chain": "ethereum",
    "rpc_endpoint": "${ETHEREUM_RPC_URL}",
    "live_transactions_allowed": false,
    "requires_funding": true,
    "constraints": ["use-mainnet-fork-for-historical-context"]
  },
  "recommended_focus": [
    "share accounting and rounding",
    "withdrawal limits and edge cases",
    "strategy debt transitions"
  ],
  "evidence_refs": [
    "https://immunefi.com/bug-bounty/yearn-finance-v3"
  ],
  "created_at": "2026-07-24T..."
}
```

**What Forge does:**
- Extracts scope details (in/out, contracts, chains)
- Determines environment requirements (framework, fork needs, RPC)
- Extracts focus areas from scope keywords
- Computes attack surface indicators
- Creates hunt package with Trinity markers

**What Forge does NOT do:**
- Execute code against targets
- Make strategy decisions
- Judge bug likelihood
- Estimate impact

### 4. Trinity: Investigation

Trinity receives clean, authorized hunt packages and investigates.

```bash
anchor hunt --package discoveries/forge/hunt_packages_2026-07-24.jsonl
```

Trinity knows:
- ✓ Target is authorized (Sentinel verified it)
- ✓ Scope is current (verified from official pages)
- ✓ Repository is correct (matched to official program)
- ✓ Environment is specified (fork, framework, RPC)
- ✓ Recommended focus areas are provided

Trinity does not:
- Question authorization (BugBot answered that)
- Guess at environment setup
- Hunt without a package
- Verify scope independently

## Authorization Lifecycle

```
discovered
    ↓
    (Scout: Found it)
    ↓
scope_unverified
    ↓
    (Sentinel: Checking platform URL, repo link, scope assets)
    ↓
scope_verified ← GATE: authorized=true
    ↓
    (Forge: Build hunt package)
    ↓
hunt_ready
    ↓
    (Trinity: Investigate)
    ↓
    ✓ signal → hypothesis → repro_attempted → ...
```

Rejections at any gate:
```
discovered
    ↓
    (Sentinel checks gates)
    ↓
    ✗ REJECTED (reason: platform_url_inaccessible, repo_mismatch, etc.)
    ↓
    (Manual review required)
```

## End-to-End Workflow

```bash
# 1. Discover programs from all platforms
python3 bounty_scout.py --all-platforms -v

# 2. Verify scope on discovered targets
python3 bounty_sentinel.py discoveries/scout/scout_immunefi_2026-07-24.jsonl -v
python3 bounty_sentinel.py discoveries/scout/scout_code4rena_2026-07-24.jsonl -v

# 3. Forge hunt packages from verified targets
python3 target_forge.py discoveries/sentinel/verified_2026-07-24.jsonl \
    --discovery-file discoveries/scout/scout_immunefi_2026-07-24.jsonl

# 4. Feed Trinity
anchor hunt --package discoveries/forge/hunt_packages_2026-07-24.jsonl
```

## Security Principles

### What BugBot Never Does
- ✗ Attack live contracts without explicit authorization
- ✗ Submit exploits automatically
- ✗ Assume old bounty pages are current scope
- ✗ Include targets without verification
- ✗ Expose findings publicly
- ✗ Test against mainnet without permission

### What BugBot Always Does
- ✓ Requires explicit authorization status
- ✓ Records verification method and evidence
- ✓ Keeps scope current with staleness tracking
- ✓ Matches repositories to official programs
- ✓ Pins to known commit hashes
- ✓ Separates discovery, verification, normalization, investigation

### Data Flow
```
Scout:   External API → Local JSON (discovered_target)
         No sensitive data, only public scope info

Sentinel: Local JSON → Local JSON (verification_result)
          Reads from platform URLs, records evidence
          No credentials stored

Forge:   Local JSON → Local JSON (hunt_package)
         Pure transformation, no external calls

Trinity: Reads hunt_packages → Investigates
         Never touches bounty platforms directly
```

## Example: Immunefi to Trinity

### Step 1: Scout Discovers Yearn

```bash
$ python3 bounty_scout.py --platform immunefi
Discovering Immunefi programs...
Found 47 Immunefi programs
  Yearn Finance v3: contracts=[0x4D75..., 0xAB2C...], payouts=$1k-$150k
  AAVE Governance: contracts=[0x7FC...], payouts=$100-$500k
  Curve Finance: contracts=[0x9...], payouts=$500-$100k
...
```

Scout output:
```jsonl
{"target_id":"yearn-v3", "program_name":"Yearn Finance v3", "platform":"immunefi", "platform_url":"https://...", "repository_url":"https://github.com/yearn/yearn-v3", "in_scope_assets":[...], "authorization_status":"scope_unverified"}
```

### Step 2: Sentinel Verifies Scope

```bash
$ python3 bounty_sentinel.py discoveries/scout/scout_immunefi_2026-07-24.jsonl

✓ yearn-v3: Verified via official_page (confidence: 0.85)
✓ aave-governance: Verified via official_page (confidence: 0.80)
✗ curve-finance: Platform URL inaccessible (confidence: 0.0)
```

Sentinel output (authorized only):
```jsonl
{"target_id":"yearn-v3", "authorized":true, "method":"official_page", "confidence":0.85, "evidence":["https://immunefi.com/bug-bounty/yearn-v3", "https://github.com/yearn/yearn-v3"], "verified_at":"2026-07-24T..."}
```

### Step 3: Forge Creates Hunt Package

```bash
$ python3 target_forge.py discoveries/sentinel/verified_2026-07-24.jsonl \
    --discovery-file discoveries/scout/scout_immunefi_2026-07-24.jsonl

Forging 2 hunt packages
  Forged: hunt_yearn_v3_001
  Forged: hunt_aave_governance_001
```

Forge output:
```jsonl
{"hunt_id":"hunt_yearn_v3_001", "target":{"program":"Yearn Finance v3", "authorized":true, ...}, "scope":{...}, "environment":{"framework":"foundry", "fork_required":true, ...}, "recommended_focus":["share accounting", "withdrawal flow"], ...}
```

### Step 4: Trinity Investigates

```bash
$ anchor hunt --package discoveries/forge/hunt_packages_2026-07-24.jsonl
Loading hunt_yearn_v3_001
  Program: Yearn Finance v3
  Authorized: true ✓
  Scope: 5 contracts in ethereum
  Framework: foundry
  Focus: share accounting, withdrawal flow
  
Generating hunt plan...
```

Trinity creates Trinity leads from each hunt package, all marked:
- `scope_status: "authorized"` (Sentinel verified it)
- Evidence refs point to official bounty page
- Environment setup is complete

## Implementation Notes

### Network Requirements
- Scout needs internet access to bounty platforms (Immunefi API, Code4rena API)
- Sentinel needs to reach platform URLs for verification
- Forge needs no network (pure transformation)
- Trinity needs RPC endpoints for the chains in scope

### Rate Limiting
- Scout: Respects API rate limits (usually 1000 reqs/day)
- Sentinel: Light network use (1 request per target)
- Forge: No network calls
- Trinity: RPC rate limiting per chain

### Staleness
- Scout: Runs periodically (daily recommended)
- Sentinel: Marks `verified_at` and `scope_expires_at`
- Forge: Inherits staleness from verification
- Trinity: Rejects stale hunt packages (> 30 days old)

## Future Enhancements

- [ ] Automatic scope re-verification on staleness timeout
- [ ] Historical bug class frequency by program
- [ ] Attack surface complexity scoring
- [ ] Estimated payout projection
- [ ] Integration with bug report database (which programs payout fastest)
- [ ] Parallel Scout + Sentinel + Forge pipeline
- [ ] Slack notifications for high-priority targets
- [ ] Automated portfolio management (don't hunt same program concurrently)

## Troubleshooting

### Scout finds nothing
```
Solution: Check that Immunefi/Code4rena APIs are accessible:
  curl https://immunefi.com/api/programs
  Check network policy for proxy restrictions
```

### Sentinel rejects everything
```
Solution: Verify that platform URLs are reachable:
  curl https://immunefi.com/bug-bounty/...
Check that repository links match official programs
```

### Forge creates packages but Trinity rejects
```
Solution: Check that hunt_package.target.authorized == true
  Verify scope_verified status from Sentinel
  Check that environment.constraints are satisfiable
```

### Trinity won't load hunt package
```
Solution: Validate package format:
  python3 -c "import json; json.load(open(package_file))"
  Check hunt_id and target.program fields are present
  Verify authorization_method is recorded
```
