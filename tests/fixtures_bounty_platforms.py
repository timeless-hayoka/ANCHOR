"""Test fixtures for bounty platform responses.

Real-world responses from Immunefi, Code4rena, Sherlock (anonymized/simplified).
Used to validate that Scout/Sentinel handle realistic platform data.
"""

from __future__ import annotations

# === IMMUNEFI FIXTURES ===

IMMUNEFI_PROGRAM_VALID = {
    "id": "yearn-v3",
    "name": "Yearn Finance v3",
    "website": "https://yearn.finance",
    "repository": "https://github.com/yearn/yearn-v3",
    "description": "Yearn Finance v3 bug bounty program",
    "inScopeAssets": [
        {
            "type": "contract",
            "address": "0x4D7590eB56c3529d67dff690d1338D0c4E6B800C",
            "label": "Yearn Vault Factory",
            "chain": "ethereum",
        },
        {
            "type": "contract",
            "address": "0xEA6bc3Cc4105f77c370A9e2e4B7346D9B6540e97",
            "label": "Yearn Strategy Manager",
            "chain": "ethereum",
        },
    ],
    "outOfScopeAssets": [
        {
            "type": "contract",
            "address": "0x0000000000000000000000000000000000000000",
            "label": "Test contracts",
            "chain": "ethereum",
        },
    ],
    "languages": ["Solidity"],
    "framework": "foundry",
    "chain": "ethereum",
    "kyc_required": False,
    "payout_range": "$1,000 - $150,000",
    "status": "active",
}

IMMUNEFI_PROGRAM_MISSING_REPO = {
    "id": "mystery-protocol",
    "name": "Mystery Protocol",
    "website": "https://mystery.local",
    "repository": None,  # MISSING
    "description": "Bug bounty with no repo link",
    "inScopeAssets": [
        {
            "type": "contract",
            "address": "0x1111111111111111111111111111111111111111",
            "label": "Main contract",
        }
    ],
    "outOfScopeAssets": [],
    "languages": ["Solidity"],
    "framework": "foundry",
    "kyc_required": False,
}

IMMUNEFI_PROGRAM_EMPTY_SCOPE = {
    "id": "empty-scope",
    "name": "Empty Scope Protocol",
    "website": "https://empty.local",
    "repository": "https://github.com/empty/protocol",
    "description": "Program with no scope defined",
    "inScopeAssets": [],  # EMPTY
    "outOfScopeAssets": [],
    "languages": ["Solidity"],
    "kyc_required": False,
}

IMMUNEFI_PROGRAM_ARCHIVED = {
    "id": "old-protocol",
    "name": "Old Protocol (Archived)",
    "website": "https://old.local",
    "repository": "https://github.com/old/protocol",
    "description": "Bounty program closed in 2024",
    "status": "archived",  # CLOSED
    "inScopeAssets": [
        {
            "type": "contract",
            "address": "0x2222222222222222222222222222222222222222",
            "label": "Old vault",
        }
    ],
    "outOfScopeAssets": [],
    "languages": ["Solidity"],
    "kyc_required": False,
}

# === CODE4RENA FIXTURES ===

CODE4RENA_CONTEST_VALID = {
    "id": "2024-07-aave-v3",
    "name": "AAVE V3 - July 2024",
    "documentation_url": "https://code4rena.com/contests/2024-07-aave-v3",
    "repository": "https://github.com/aave/aave-v3-core",
    "status": "open",
    "start_time": "2024-07-15T00:00:00Z",
    "end_time": "2024-07-29T23:59:59Z",
    "prize_pool": "$150,000",
    "in_scope_files": [
        {
            "path": "contracts/core/Pool.sol",
            "name": "Main Pool Contract",
        },
        {
            "path": "contracts/core/PoolConfigurator.sol",
            "name": "Pool Configurator",
        },
    ],
    "out_of_scope_files": [
        {
            "path": "contracts/test/**",
            "name": "Test files",
        },
    ],
    "framework": "foundry",
    "chain": "ethereum",
    "kyc_required": True,
}

CODE4RENA_CONTEST_EXPIRED = {
    "id": "2024-01-old-contest",
    "name": "Old Contest - January 2024",
    "documentation_url": "https://code4rena.com/contests/2024-01-old",
    "repository": "https://github.com/old/protocol",
    "status": "finished",  # CLOSED
    "end_time": "2024-01-31T23:59:59Z",
    "prize_pool": "$50,000",
    "in_scope_files": [
        {
            "path": "contracts/main.sol",
            "name": "Main contract",
        }
    ],
    "out_of_scope_files": [],
    "framework": "hardhat",
    "chain": "ethereum",
    "kyc_required": False,
}

CODE4RENA_CONTEST_MISSING_FILES = {
    "id": "2024-07-malformed",
    "name": "Malformed Contest",
    "documentation_url": "https://code4rena.com/contests/2024-07-malformed",
    "repository": "https://github.com/malformed/protocol",
    "status": "open",
    "in_scope_files": [],  # EMPTY
    "out_of_scope_files": [],
    "framework": "foundry",
    "chain": "ethereum",
    "kyc_required": False,
}

# === EDGE CASES & NEGATIVE FIXTURES ===

# Correct project name but wrong repository
MISMATCHED_REPO = {
    "id": "yearn-v3",
    "name": "Yearn Finance v3",
    "website": "https://yearn.finance",
    "repository": "https://github.com/malicious/yearn-v3",  # WRONG OWNER
    "inScopeAssets": [
        {
            "type": "contract",
            "address": "0x4D7590eB56c3529d67dff690d1338D0c4E6B800C",
            "label": "Yearn Vault Factory",
        }
    ],
    "framework": "foundry",
}

# Shortened/redirected repository link
SHORTENED_REPO_LINK = {
    "id": "shortened-repo",
    "name": "Protocol with Shortened Link",
    "website": "https://protocol.local",
    "repository": "https://bit.ly/protocol-repo",  # SHORTENED
    "inScopeAssets": [
        {"type": "contract", "address": "0x3333333333333333333333333333333333333333"}
    ],
    "framework": "foundry",
}

# Multiple repositories listed (ambiguous)
MULTIPLE_REPOS = {
    "id": "multi-repo",
    "name": "Multi-Repo Protocol",
    "website": "https://multi.local",
    "repository": [  # ARRAY instead of string
        "https://github.com/org/protocol-v1",
        "https://github.com/org/protocol-v2",
        "https://github.com/org/protocol-v3",
    ],
    "inScopeAssets": [
        {"type": "contract", "address": "0x4444444444444444444444444444444444444444"}
    ],
    "framework": "foundry",
}

# Scope page and repository disagree
SCOPE_REPO_DISAGREE = {
    "id": "disagree",
    "name": "Disagreeing Scope",
    "website": "https://disagree.local",
    "repository": "https://github.com/org/protocol",
    "scope_page_says": "v3.5 contracts on Ethereum",
    "repository_default_branch": "main",
    "repository_latest_tag": "v2.1",  # DIFFERENT VERSION
    "inScopeAssets": [
        {"type": "contract", "address": "0x5555555555555555555555555555555555555555"}
    ],
    "framework": "foundry",
}

# Cloudflare/bot challenge (HTML instead of JSON)
CLOUDFLARE_CHALLENGE = {
    "status": 403,
    "headers": {
        "Content-Type": "text/html",
        "Server": "cloudflare",
    },
    "body": "<html><body>Please complete the security check</body></html>",
}

# Redirect to login
REDIRECT_TO_LOGIN = {
    "status": 302,
    "headers": {
        "Location": "https://immunefi.com/login",
    },
}

# HTTP 200 but contains error
ERROR_PAGE_200 = {
    "status": 200,
    "headers": {"Content-Type": "application/json"},
    "body": {
        "error": "Program not found",
        "message": "The requested program does not exist",
    },
}

# Incomplete/truncated response
INCOMPLETE_RESPONSE = {
    "id": "incomplete",
    "name": "Incomplete Program",
    # Missing: repository, inScopeAssets, framework, etc.
}

# === REPOSITORY FIXTURES ===

GITHUB_REPO_VALID = {
    "id": 12345678,
    "owner": {"login": "yearn"},
    "name": "yearn-v3",
    "full_name": "yearn/yearn-v3",
    "html_url": "https://github.com/yearn/yearn-v3",
    "description": "Yearn Finance V3",
    "default_branch": "main",
    "topics": ["security", "smart-contract", "ethereum"],
    "archived": False,
}

GITHUB_REPO_ARCHIVED = {
    "id": 87654321,
    "owner": {"login": "old-org"},
    "name": "old-protocol",
    "full_name": "old-org/old-protocol",
    "html_url": "https://github.com/old-org/old-protocol",
    "default_branch": "main",
    "archived": True,  # ARCHIVED
}

GITHUB_REPO_FORK = {
    "id": 11223344,
    "owner": {"login": "attacker"},
    "name": "yearn-v3",
    "full_name": "attacker/yearn-v3",
    "html_url": "https://github.com/attacker/yearn-v3",
    "fork": True,  # IS A FORK
    "parent": {
        "full_name": "yearn/yearn-v3",
        "owner": {"login": "yearn"},
    },
}

# === COMMIT FIXTURES ===

COMMIT_VALID = {
    "sha": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
    "commit": {
        "author": {
            "name": "Developer",
            "email": "dev@yearn.finance",
            "date": "2026-07-15T10:30:00Z",
        },
        "message": "Merge pull request #1234 from yearn/feature/v3-upgrade",
    },
    "html_url": "https://github.com/yearn/yearn-v3/commit/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
}

# === TEMPLATES FOR SENTINEL TESTING ===

# What Sentinel should accept
SENTINEL_ACCEPT_CRITERIA = {
    "platform_url_accessible": True,
    "repository_linked": True,
    "in_scope_assets": len([]) > 0,  # Must have at least one
    "confidence": 0.7,  # >= 0.7
    "not_archived": True,
    "not_redirected": True,
}

# What Sentinel should reject
SENTINEL_REJECT_CRITERIA = [
    ("platform_url_inaccessible", False),
    ("repository_not_linked", False),
    ("in_scope_assets_empty", False),
    ("confidence_too_low", False),
    ("program_archived", False),
    ("redirects_to_login", False),
    ("cloudflare_challenge", False),
    ("malformed_json", False),
    ("incomplete_response", False),
]
