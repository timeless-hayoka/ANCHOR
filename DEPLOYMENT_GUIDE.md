# BugBot Deployment Guide

## Overview

BugBot is a strict authorization pipeline for finding smart contract bugs on authorized bounty programs. It prevents Trinity from ever hunting unauthorized targets by enforcing multiple hard gates.

**Pipeline**: Scout → Sentinel → Forge → Trinity

## Prerequisites

- Python 3.11+
- Internet access to bounty platforms (Immunefi, Code4rena, Sherlock, etc.)
- Git
- Foundry or Hardhat (for testing environments)
- RPC endpoints for target chains (Ethereum, Arbitrum, Polygon, etc.)

## Installation

```bash
# Clone repository
git clone https://github.com/your-org/ANCHOR.git
cd ANCHOR

# Install dependencies (if any)
pip3 install -r requirements.txt  # (if needed)

# Verify tests pass
python3 -m pytest tests/test_bounty_crawler_strict.py -v
python3 -m pytest tests/test_bounty_sentinel_validation.py -v
```

## Configuration

### 1. Set RPC Endpoints

Hunt packages reference RPC endpoints via environment variables (never hardcoded URLs).

```bash
# ~/.env or export in shell
export ETHEREUM_RPC_URL="https://eth-mainnet.alchemyapi.io/v2/YOUR_KEY"
export ARBITRUM_RPC_URL="https://arbitrum-mainnet.infura.io/v3/YOUR_KEY"
export POLYGON_RPC_URL="https://polygon-mainnet.infura.io/v3/YOUR_KEY"
export OPTIMISM_RPC_URL="https://optimism-mainnet.infura.io/v3/YOUR_KEY"
export BASE_RPC_URL="https://base-mainnet.infura.io/v3/YOUR_KEY"
export SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"
```

**Critical**: Never embed API keys in code or configuration files. Use environment variables.

## Usage

### Phase 1: Discover Programs (Scout)

Scout queries official bounty platforms and discovers programs.

```bash
# Discover from Immunefi
python3 bounty_scout.py --platform immunefi --output discoveries/scout/immunefi_programs.jsonl

# Discover from Code4rena
python3 bounty_scout.py --platform code4rena --output discoveries/scout/code4rena_contests.jsonl

# Combine all platforms
python3 bounty_scout.py --all --output discoveries/scout/all_programs.jsonl
```

Output: JSONL file with discovered targets marked `scope_unverified`.

### Phase 2: Verify Scope (Sentinel)

Sentinel verifies each target against official bounty platform pages.

```bash
python3 bounty_sentinel.py discoveries/scout/all_programs.jsonl \
  --output-dir discoveries/sentinel \
  -v

# Output: verified_YYYY-MM-DD.jsonl (only authorized targets)
# Output: rejected_YYYY-MM-DD.jsonl (rejection reasons)
```

**Hard Gates** (must all pass):
- ✓ Platform URL is accessible
- ✓ Repository URL provided
- ✓ In-scope assets defined (not empty)
- ✓ Verification confidence ≥ 0.7
- ✓ No negative signals (not archived, educational, unaudited, etc.)

### Phase 3: Normalize Packages (Forge)

Forge converts verified targets into hunt packages for Trinity.

```bash
python3 target_forge.py discoveries/sentinel/verified_YYYY-MM-DD.jsonl \
  --discovery-file discoveries/scout/all_programs.jsonl \
  --output-dir discoveries/forge \
  -v

# Output: hunt_packages_YYYY-MM-DD.jsonl
```

Each hunt package includes:
- ✓ Authorization proof
- ✓ Commit SHA (pinned version)
- ✓ Scope definition
- ✓ Environment specs (framework, fork requirements)
- ✓ Focus areas (recommended attack surface)
- ✓ RPC endpoint references (via env vars, not hardcoded)

### Phase 4: Start Hunting (Trinity)

Trinity receives hunt packages and begins investigation.

```bash
# Feed hunt packages to Trinity
python3 -m anchor hunt --package discoveries/forge/hunt_packages_YYYY-MM-DD.jsonl

# Or start hunting a specific package
python3 -m anchor hunt --hunt-id hunt_yearn_v3_001_001
```

Trinity will:
1. Verify authorization before starting
2. Set up forked environment
3. Load scope and focus areas
4. Begin hypothesis testing
5. Report findings to specified bounty platform

## Validation

### Verify Pipeline Locally

```bash
# Run end-to-end validation with mock data
python3 validate_bugbot_pipeline.py
```

Expected output:
- ✓ Scout discovers programs
- ✓ Sentinel authorizes
- ✓ Forge creates hunt packages
- ✓ Trinity ready for investigation

### Test Authorization Strictness

```bash
# Run strict crawler tests
python3 -m pytest tests/test_bounty_crawler_strict.py -v

# Expected: All 11 tests pass
# Validates: False positives are rejected
#   - Security tools without bounty programs
#   - Educational materials
#   - Archived/unaudited programs
#   - Writeups and post-mortems
```

### Test Scope Verification

```bash
# Run sentinel validation tests
python3 -m pytest tests/test_bounty_sentinel_validation.py -v

# Expected: All 17 tests pass
# Validates: Fail-closed behavior
#   - Rejects missing repository URLs
#   - Rejects empty scope assets
#   - Rejects low confidence
#   - Accepts only verified programs
```

## Safety Mechanisms

### 1. Authorization Gating

Only AUTHORIZED_ASSET_MATCHED targets reach Trinity:

```
UNCONFIRMED          → Rejected (no bounty evidence)
PUBLIC_REVIEW_ONLY   → Rejected (writeups, not bounty)
PROGRAM_FOUND_...    → Rejected (asset mismatch)
AUTHORIZED_ASSET_... → ✓ ACCEPTED (explicit bounty link)
EXPIRED_OR_ARCHIVED  → Rejected (program closed)
CONTRADICTED         → Rejected (negative signals override)
```

### 2. Negative Signal Blocking

Negative signals override even explicit bounty links:
- `educational` - Learning platforms, demo projects
- `no_bounty` - Explicit "no bounty" disclaimers
- `archived` - Deprecated or no longer maintained
- `audit_planned` - "Audit scheduled for Q3" (not yet audited)
- `not_audited` - "This code is unaudited"
- `mainnet_blocked` - Production use prohibited
- `writeup` - Security post-mortems, incident reports

### 3. Commit Pinning

Hunt packages include full 40-character commit SHA resolved from GitHub API. Trinity never hunts floating branches.

### 4. RPC Environment Variables

RPC endpoints are referenced via environment variables, never hardcoded:
```
target.rpc_env_var: "ETHEREUM_RPC_URL"
environment.rpc_endpoint: "${ETHEREUM_RPC_URL}"
```

Trinity resolves at runtime from `$ETHEREUM_RPC_URL`.

### 5. Scope Validation

Each hunt package includes:
- In-scope assets (contracts, functions, domains)
- Out-of-scope assets
- Forbidden methods
- KYC requirements

## Monitoring and Logging

Enable verbose logging to track authorization decisions:

```bash
python3 bounty_scout.py --all -v
python3 bounty_sentinel.py discoveries/scout/all_programs.jsonl -v
python3 target_forge.py discoveries/sentinel/verified_YYYY-MM-DD.jsonl -v
```

Log files track:
- Platform API responses
- Scope verification results
- Authorization evidence
- Rejection reasons

## Troubleshooting

### "Platform URL inaccessible"
Check network connectivity and platform status:
```bash
curl -I https://immunefi.com/bug-bounty/
curl -I https://code4rena.com/api/contests
```

### "Confidence below threshold (0.7)"
Sentinel couldn't verify scope. Check:
- Platform URL is correct
- Repository URL is provided
- In-scope assets are defined

### "No matches for commit SHA"
GitHub API couldn't resolve commit. Check:
- Repository exists and is public
- Commit hash is valid
- GitHub API rate limits not exceeded

### "RPC endpoint env var not set"
Trinity can't access blockchain. Set required env vars:
```bash
export ETHEREUM_RPC_URL="..."
```

## Production Checklist

- [ ] All tests pass locally
- [ ] RPC endpoints configured and tested
- [ ] Network access to bounty platforms verified
- [ ] Scout discovers programs successfully
- [ ] Sentinel rejects at least 1 false positive (validation)
- [ ] Forge creates hunt packages
- [ ] Trinity ingests packages without authorization errors
- [ ] Logging enabled and monitored
- [ ] Backups of discoveries in place

## Next Steps

1. **Deploy**: Run on internet-connected machine
2. **Scout**: Discover bounty programs from official platforms
3. **Verify**: Sentinel confirms authorization
4. **Prepare**: Forge normalizes to hunt packages
5. **Hunt**: Trinity begins investigation
6. **Report**: Submit findings to bounty platforms
7. **Earn**: Collect bounty rewards

## Support

For authorization questions, check BUGBOT_SUITE.md for detailed architecture.

For Trinity integration issues, consult Trinity documentation.
