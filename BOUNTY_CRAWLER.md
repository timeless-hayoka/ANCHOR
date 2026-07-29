# ANCHOR Bounty Crawler

Automated discovery and Trinity-formatted lead generation for smart contract bug bounties.

## Overview

The bounty crawler automatically discovers potential security vulnerabilities in public smart contract repositories by:

1. **Repository Discovery** - Search GitHub for repositories matching security-focused keywords or browse specific organizations
2. **Issue Extraction** - Fetch issues and discussions from discovered repositories
3. **Signal Extraction** - Identify potential bug signals using pattern matching (reentrancy, access control, accounting, oracle issues, etc.)
4. **Lead Generation** - Convert discovered issues to Trinity-formatted leads for structured review

## Installation

The crawler uses only Python standard library + existing ANCHOR dependencies:

```bash
python3 bounty_crawler.py --help
```

## Usage

### Search by Bug Profile

Crawl repositories matching a specific security profile:

```bash
# Search for access control vulnerabilities
python3 bounty_crawler.py --profile auth --limit 20

# Search for accounting and rounding issues
python3 bounty_crawler.py --profile accounting --limit 20

# Available profiles: auth, accounting, oracle, upgrade
```

### Crawl Organization

Discover issues across an entire GitHub organization:

```bash
# Crawl Solana Foundation repos
python3 bounty_crawler.py --org solana --limit 50 -v

# Crawl OpenZeppelin repos  
python3 bounty_crawler.py --org OpenZeppelin --limit 50
```

### Scope-Gated Crawling

Only generate leads for authorized targets (requires scope grants):

```bash
# Crawl but only include authorized targets
python3 bounty_crawler.py --profile auth --scope-check --limit 30
```

This filters results to only repositories for which an active `scope/active_grant.json` exists and matches the target.

### GitHub Authentication

Provide a GitHub token to increase rate limits from 60/hr to 5000/hr:

```bash
# Via environment variable
export GITHUB_TOKEN="ghp_..."
python3 bounty_crawler.py --org solana --limit 100

# Via command-line argument
python3 bounty_crawler.py --token "ghp_..." --profile oracle --limit 50
```

### Custom Output

Save discovered leads to a specific file:

```bash
python3 bounty_crawler.py \
  --profile auth \
  --limit 20 \
  --output-file audit_results.jsonl \
  --output-dir /tmp/leads
```

## Bug Profiles

### `auth` - Authorization Boundary
Detects potential access control and permission bypass vulnerabilities.
- **Keywords**: authorization, permission, owner, role, access control
- **Signals**: missing checks, wrapper functions, caller identity changes

### `accounting` - Accounting & Rounding
Detects balance tracking, rounding, and precision issues.
- **Keywords**: balance, share, account, precision, dust, drift
- **Signals**: accounting drift, rounding errors, share/balance mismatches

### `oracle` - Oracle & Input Validation
Detects oracle manipulation and stale price issues.
- **Keywords**: oracle, price feed, stale, delay, manipulation
- **Signals**: stale prices, invalid inputs, harmful decisions

### `upgrade` - Proxy & Initialization
Detects upgradeability and initialization vulnerabilities.
- **Keywords**: proxy, upgrade, implementation, initializer
- **Signals**: double initialization, upgrade authority issues, state divergence

## Output Format

Discovered leads are saved as JSONL (one Trinity lead record per line):

```json
{
  "schema_version": "1.0",
  "lead_id": "lead_solana_anchor_1234",
  "target": "solana/anchor",
  "scope_status": "unknown",
  "state": "signal",
  "title": "Missing access control in admin function (solana/anchor)",
  "claim": "GitHub issue #1234 on solana/anchor suggests a potential auth vulnerability...",
  "scope": "Target: solana/anchor. Authorized scope status unknown...",
  "mechanism": "The upgrade function lacks permission verification...",
  "falsifier": "If the code already contains the fix or mitigation...",
  "repro_plan": "1. Verify authorization for solana/anchor\n2. Clone the repository...",
  "impact_boundary": "",
  "evidence_refs": ["https://github.com/solana/anchor/issues/1234"],
  "review_refs": [],
  "created_at": "2026-07-24T...",
  "updated_at": "2026-07-24T...",
  "events": []
}
```

## Next Steps

After running the crawler, review and process discovered leads:

```bash
# View a specific lead
anchor lead show lead_solana_anchor_1234

# View all leads in a file
while IFS= read -r line; do
  lead_id=$(echo "$line" | jq -r '.lead_id')
  echo "=== $lead_id ==="
  echo "$line" | jq '.title, .claim'
done < discoveries/crawler/crawl_*.jsonl

# Process leads programmatically
python3 -c "
import json
for line in open('discoveries/crawler/crawl_2026-07-24.jsonl'):
    lead = json.loads(line)
    if 'access control' in lead['claim'].lower():
        print(f'[{lead[\"target\"]}] {lead[\"title\"]}')"
```

## Workflow Integration

The crawled leads integrate with ANCHOR's Trinity state machine:

1. **Signal State** - Newly discovered issues arrive as `signal` leads
2. **Scope Check** - `scope_status` is `unknown` until verified
3. **Hypothesis** - Review the extracted claim, mechanism, and falsifier
4. **Manual Review** - Use `anchor lead show` or edit leads for authorization
5. **Promotion** - Apply `apply_transition` to move leads through the Trinity lifecycle

Example promotion workflow:

```python
from trinity_lead_state_machine import LeadRecord, apply_transition
import json

# Load a crawled lead
with open("discoveries/crawler/crawl_2026-07-24.jsonl") as f:
    lead_data = json.loads(f.readline())
    lead = LeadRecord.from_dict(lead_data)

# Update scope status after authorization check
lead.scope_status = "authorized"

# Promote to hypothesis once reviewed
lead = apply_transition(
    lead,
    to_state="hypothesis",
    actor="security_team",
    reason="Reviewed issue context and extracted falsifiable hypothesis",
    event_id="evt_promote_1",
)
```

## Performance & Rate Limiting

- **Unauthenticated**: 60 requests/hour (GitHub API public limit)
- **Authenticated**: 5,000 requests/hour (with GITHUB_TOKEN)
- **Courtesy delay**: 1 second per keyword search, 0.5 second per organization repo

Typical crawl times:
- Single profile (20 repos): ~30-60 seconds  
- Organization (50 repos): ~60-120 seconds
- Multiple profiles: Add ~30s per profile

## Troubleshooting

### Rate Limited
```
Rate limit approaching, waiting Xs
```
**Solution**: Provide a GITHUB_TOKEN or reduce `--limit`

### Network Issues
```
[Errno 111] Connection refused
```
**Solution**: Check internet connection; crawler requires internet access

### Empty Results
- Issue: No issues discovered in crawl
- **Likely cause**: Repositories are archived or have no open issues
- **Solution**: Increase `--limit` or try different `--profile`

### Scope Check Failing
```
Skipped (not authorized)
```
**Solution**: Run without `--scope-check` for exploratory crawling, or create scope grants in `scope/active_grant.json`

## Architecture

### GitHubClient
Minimal REST API client handling:
- Repository search and organization browsing
- Issue fetching with rate limit tracking
- Automatic token-based authentication

### BugSignalExtractor
Pattern-based signal detection:
- Regex patterns for each bug category
- Severity classification (critical, high, medium, low)
- Relevance scoring (multiple signals + severity)

### BountyCrawler
Main orchestration:
- Keyword profile and organization crawling
- Lead generation from discovered issues
- JSONL output persistence

## Security Notes

- Crawler only reads public GitHub repositories
- No credentials or private data are extracted
- Scope authorization is advisory (for planning-only mode)
- All discoveries are saved locally before review

## Contributing

To add new bug profiles, extend `CRAWLER_KEYWORDS` and `BugSignalExtractor.PATTERNS`:

```python
CRAWLER_KEYWORDS = {
    "new_category": [
        "keyword1 phrase",
        "keyword2 phrase",
    ],
}

BugSignalExtractor.PATTERNS = {
    "new_signal": re.compile(r"pattern|alternative", re.I),
}
```

Then test the new patterns:

```bash
python3 -m pytest tests/test_bounty_crawler.py -v
```
