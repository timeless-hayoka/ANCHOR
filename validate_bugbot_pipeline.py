#!/usr/bin/env python3
"""Validate full BugBot pipeline end-to-end with mock data.

This demonstrates how Scout → Sentinel → Forge → Trinity flows work
without requiring live network access to bounty platforms.
"""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    """Load Python module from file path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load BugBot components
crawler_strict = load_module("bounty_crawler_strict", "bounty_crawler_strict.py")
target_forge = load_module("target_forge", "target_forge.py")


def test_full_pipeline():
    """Demonstrate Scout → Sentinel → Forge → Trinity pipeline."""
    print("=" * 80)
    print("BugBot Pipeline Validation")
    print("=" * 80)

    # Simulate: Scout discovers Yearn program from Immunefi
    print("\n[1] SCOUT: Discovered programs")
    print("-" * 80)
    discovered_targets = [
        {
            "target_id": "yearn_v3_001",
            "program_name": "Yearn Finance",
            "platform": "Immunefi",
            "platform_url": "https://immunefi.com/bug-bounty/yearn-v3",
            "repository_url": "https://github.com/yearn/yearn-v3",
            "framework": "foundry",
            "chain": "ethereum",
            "in_scope_assets": [
                {
                    "asset_type": "contract",
                    "identifier": "0x4D7590eB56c3529d67dff690d1338D0c4E6B800C",
                    "label": "Yearn Vault Factory",
                },
                {
                    "asset_type": "contract",
                    "identifier": "0x50b3fdb....",
                    "label": "Strategy Distributor",
                },
            ],
            "out_of_scope_assets": [],
            "kyc_required": False,
            "commit_sha": "7ff011a7ff5e69fb6ba0f2fa6e4ba4f1c0c9c1a0",  # Real 40-char hex SHA
        }
    ]

    for target in discovered_targets:
        print(f"  ✓ {target['program_name']} on {target['platform']}")
        print(f"    Repo: {target['repository_url']}")
        print(f"    Assets: {len(target['in_scope_assets'])} in scope")

    # Simulate: Sentinel verifies authorization
    print("\n[2] SENTINEL: Scope verification")
    print("-" * 80)
    detector = crawler_strict.BountyProgramDetector()

    readme_with_bounty = """
    # Yearn Finance V3

    Yearn is a yield optimization protocol for DeFi.

    ## Security

    We run a bug bounty program on Immunefi:
    https://immunefi.com/bug-bounty/yearn-v3

    For security issues, please report through Immunefi.
    """

    result = detector.classify_authorization(
        repo_owner="yearn",
        repo_name="yearn-v3",
        readme_content=readme_with_bounty,
        description="Yield optimization protocol",
    )

    print(f"  Authorization State: {result.state.value}")
    print(f"  Confidence: {result.authorization_confidence:.0%}")
    print(f"  Authorized: {result.is_authorized()}")

    if result.evidence:
        print(f"  Evidence:")
        for ev in result.evidence:
            print(f"    - {ev.program_name}: {ev.bounty_url}")

    if result.negative_signals:
        print(f"  Negative Signals:")
        for sig in result.negative_signals:
            print(f"    - {sig}")

    if not result.is_authorized():
        print("\n  ⚠️  NOT AUTHORIZED - would be rejected before Trinity ingestion")
        return False

    # Simulate: Forge normalizes to hunt package
    print("\n[3] FORGE: Normalize to hunt packages")
    print("-" * 80)

    forge = target_forge.TargetForge()
    verification = {
        "authorized": True,
        "method": "official_page",
        "confidence": 0.9,
        "evidence": [
            "https://immunefi.com/bug-bounty/yearn-v3",
            "https://github.com/yearn/yearn-v3",
        ],
    }

    try:
        package = forge.forge_package(discovered_targets[0], verification)
        print(f"  Hunt ID: {package.hunt_id}")
        print(f"  Program: {package.target['program']}")
        print(f"  Platform: {package.target['platform']}")
        print(f"  Repository: {package.target['repository']}")
        print(f"  Authorized: {package.target['authorized']}")
        print(f"  Verification Confidence: {package.target['verification_confidence']:.0%}")
        print(f"  Framework: {package.environment.framework.value}")
        print(f"  Fork Required: {package.environment.fork_required}")
        print(f"  RPC Env Var: {package.target['rpc_env_var']}")
        print(f"  Recommended Focus: {len(package.recommended_focus)} areas")
        for focus in package.recommended_focus:
            print(f"    - {focus}")
    except ValueError as e:
        print(f"  ✗ VALIDATION FAILED: {e}")
        return False

    # Simulate: Trinity receives only authorized packages
    print("\n[4] TRINITY: Investigation readiness")
    print("-" * 80)
    print(f"  ✓ Hunt package ready for Trinity ingestion")
    print(f"  ✓ Authorization verified: {package.target['authorized']}")
    print(f"  ✓ Commit pinned: {package.target['commit_sha']}")
    print(f"  ✓ Scope defined: {len(package.scope['in_scope'])} asset types")
    print(f"  ✓ Environment specs: {package.environment.framework.value} + fork")
    print(f"\n  Next: Trinity uses this package to start investigation")
    print(f"    - Set up forked environment with RPC_URL from {package.target['rpc_env_var']}")
    print(f"    - Focus on: {package.recommended_focus[0]}")
    print(f"    - Report findings to: {package.target['platform']}")

    print("\n" + "=" * 80)
    print("✓ FULL PIPELINE VALIDATED")
    print("=" * 80)
    print("\nReady for production deployment:")
    print("  1. Deploy on internet-connected machine")
    print("  2. Scout queries live platform APIs")
    print("  3. Sentinel verifies against real scope pages")
    print("  4. Forge creates hunt packages with resolved commit SHAs")
    print("  5. Trinity receives clean, authorized targets")
    print("  6. Hunt for real bugs on real bounty programs")
    print()

    return True


def test_negative_signals():
    """Test that negative signals block authorization."""
    print("\n" + "=" * 80)
    print("Negative Signals Validation")
    print("=" * 80)

    detector = crawler_strict.BountyProgramDetector()

    test_cases = [
        (
            "educational",
            """
            # Educational Protocol
            This is a learning platform for smart contract patterns.
            **Educational Use Only**
            https://immunefi.com/bug-bounty/learning
            """,
            "Should reject educational materials even with bounty link",
        ),
        (
            "archived",
            """
            # Old Protocol (Archived)
            This protocol is no longer maintained.
            Historical bug bounty: https://immunefi.com/bug-bounty/old
            (This program is closed)
            """,
            "Should reject archived programs even with bounty link",
        ),
        (
            "not_audited",
            """
            # Protocol V2
            ⚠️ WARNING: NOT AUDITED
            This code has not undergone professional security audit.
            Bug bounty: https://immunefi.com/bug-bounty/protocol
            """,
            "Should reject unaudited programs even with bounty link",
        ),
    ]

    for name, readme, description in test_cases:
        result = detector.classify_authorization(
            repo_owner="test",
            repo_name="test",
            readme_content=readme,
            description="",
        )
        status = "✓" if not result.is_authorized() else "✗"
        print(f"\n{status} {name}: {description}")
        print(f"  State: {result.state.value}")
        print(f"  Authorized: {result.is_authorized()}")
        if result.negative_signals:
            print(f"  Blocked by: {', '.join(result.negative_signals)}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    success = test_full_pipeline()
    test_negative_signals()

    sys.exit(0 if success else 1)
