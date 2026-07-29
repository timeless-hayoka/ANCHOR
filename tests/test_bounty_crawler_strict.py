"""Tests for strict bounty crawler - regression fixtures for false positives."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


crawler_strict = load_module("bounty_crawler_strict", "bounty_crawler_strict.py")


class TestStrictCrawlerRejectsRedHerring(unittest.TestCase):
    """These repositories should NOT be marked as authorized bounty targets."""

    def setUp(self):
        self.detector = crawler_strict.BountyProgramDetector()

    def test_rejects_security_tool_repo(self):
        """A security tool (hookriisk) is not a bounty target."""
        readme = """
        # HookRisk - Webhook Security Scanner

        A tool for auditing and testing webhook implementations.

        ## Features
        - Webhook validation
        - Security testing
        - Audit trail

        ## License
        MIT
        """
        description = "Webhook security audit tool"

        result = self.detector.classify_authorization(
            repo_owner="security-org",
            repo_name="hookrisk",
            readme_content=readme,
            description=description,
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.UNCONFIRMED)
        self.assertFalse(result.is_authorized())
        self.assertEqual(len(result.evidence), 0)

    def test_rejects_writeups_repo(self):
        """Security writeups are educational, not authorized bounties."""
        readme = """
        # Web3 Security Writeups

        Collection of smart contract security analysis and audit writeups.

        ## Contents
        - OpenZeppelin audit writeups
        - Trail of Bits findings
        - Post-mortem incident analysis
        - Security best practices
        """
        description = "Smart contract audit writeups and security research"

        result = self.detector.classify_authorization(
            repo_owner="security-research",
            repo_name="web3-security-writeups",
            readme_content=readme,
            description=description,
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.CONTRADICTED)
        self.assertFalse(result.is_authorized())
        self.assertIn("writeup", result.negative_signals)

    def test_rejects_educational_platform(self):
        """Educational platform is not a bounty target."""
        readme = """
        # Compliant Asset Platform - Educational Edition

        A learning platform for compliance and asset management.

        **Educational Use Only**

        This is not production code and not suitable for real assets.

        ## Purpose
        - Learn blockchain basics
        - Practice smart contract patterns
        - Educational exercises
        """
        description = "Educational smart contract platform"

        result = self.detector.classify_authorization(
            repo_owner="education",
            repo_name="compliant-asset-platform",
            readme_content=readme,
            description=description,
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.CONTRADICTED)
        self.assertFalse(result.is_authorized())
        self.assertIn("educational", result.negative_signals)

    def test_rejects_audit_preparation(self):
        """"Audit planned" means not yet authorized."""
        readme = """
        # Shibui - DeFi Protocol

        ## Security

        We are committed to security.
        An external audit is planned for Q3 2026.
        Currently the code is not audited.

        **Do not use in production.**
        """
        description = "DeFi protocol (audit planned)"

        result = self.detector.classify_authorization(
            repo_owner="shibui-org",
            repo_name="shibui",
            readme_content=readme,
            description=description,
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.CONTRADICTED)
        self.assertFalse(result.is_authorized())
        self.assertIn("audit_planned", result.negative_signals)

    def test_rejects_not_audited_disclaimer(self):
        """Explicit "not audited" = not authorized."""
        readme = """
        # Protocol V2

        ## ⚠️ WARNING: NOT AUDITED

        This code has not undergone professional security audit.
        Use at your own risk.
        """

        result = self.detector.classify_authorization(
            repo_owner="unaudited-org",
            repo_name="protocol-v2",
            readme_content=readme,
            description="",
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.CONTRADICTED)
        self.assertFalse(result.is_authorized())
        self.assertIn("not_audited", result.negative_signals)


class TestStrictCrawlerAcceptsValid(unittest.TestCase):
    """Only explicit bounty program URLs should be authorized."""

    def setUp(self):
        self.detector = crawler_strict.BountyProgramDetector()

    def test_accepts_immunefi_program_link(self):
        """Explicit Immunefi link = authorized."""
        readme = """
        # Yearn Finance

        ## Bug Bounty

        We run a bug bounty program on Immunefi.

        **[Immunefi Bug Bounty](https://immunefi.com/bug-bounty/yearn-v3)**

        For security issues, please report through Immunefi.
        """

        result = self.detector.classify_authorization(
            repo_owner="yearn",
            repo_name="yearn-v3",
            readme_content=readme,
            description="",
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.AUTHORIZED_ASSET_MATCHED)
        self.assertTrue(result.is_authorized())
        self.assertGreater(len(result.evidence), 0)
        self.assertEqual(result.evidence[0].program_name, "Immunefi")

    def test_accepts_code4rena_contest_link(self):
        """Explicit Code4rena link = authorized."""
        readme = """
        # AAVE V3

        ## Security

        Participate in our Code4rena contest:

        [Code4rena - AAVE V3 - July 2024](https://code4rena.com/contests/2024-07-aave-v3)
        """

        result = self.detector.classify_authorization(
            repo_owner="aave",
            repo_name="aave-v3-core",
            readme_content=readme,
            description="",
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.AUTHORIZED_ASSET_MATCHED)
        self.assertTrue(result.is_authorized())
        self.assertEqual(result.evidence[0].program_name, "Code4rena")

    def test_accepts_sherlock_protocol(self):
        """Sherlock protocol link = authorized."""
        readme = """
        # Protocol X

        Security competitions on Sherlock:
        [Sherlock - Protocol X Competition](https://sherlock.xyz/competitions/protocol-x)
        """

        result = self.detector.classify_authorization(
            repo_owner="protocol-x",
            repo_name="contracts",
            readme_content=readme,
            description="",
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.AUTHORIZED_ASSET_MATCHED)
        self.assertTrue(result.is_authorized())
        self.assertEqual(result.evidence[0].program_name, "Sherlock")


class TestStrictCrawlerNegativeSignals(unittest.TestCase):
    """Negative signals override even explicit bounty links."""

    def setUp(self):
        self.detector = crawler_strict.BountyProgramDetector()

    def test_archived_program_contradicts_link(self):
        """Even if link exists, "archived" = no authorization."""
        readme = """
        # Old Protocol (Archived)

        This protocol has been archived and is no longer maintained.

        Historical bug bounty: https://immunefi.com/bug-bounty/old-protocol
        (This program is closed)
        """

        result = self.detector.classify_authorization(
            repo_owner="old-org",
            repo_name="old-protocol",
            readme_content=readme,
            description="",
        )

        # Evidence exists, but negative signal overrides
        self.assertEqual(result.state, crawler_strict.AuthorizationState.CONTRADICTED)
        self.assertFalse(result.is_authorized())
        self.assertIn("archived", result.negative_signals)

    def test_educational_disclaimer_contradicts_link(self):
        """Educational use overrides bounty link."""
        readme = """
        # Practice Protocol

        Bug bounty for learning:
        https://immunefi.com/bug-bounty/practice-protocol

        **Educational Use Only - Not for Production**

        This is a learning exercise, not a real protocol.
        """

        result = self.detector.classify_authorization(
            repo_owner="learn-org",
            repo_name="practice-protocol",
            readme_content=readme,
            description="",
        )

        self.assertEqual(result.state, crawler_strict.AuthorizationState.CONTRADICTED)
        self.assertFalse(result.is_authorized())
        self.assertIn("educational", result.negative_signals)


class TestStrictCrawlerScores(unittest.TestCase):
    """Verify scoring is separate: technical interest ≠ authorization."""

    def setUp(self):
        self.detector = crawler_strict.BountyProgramDetector()

    def test_technical_interest_separate_from_authorization(self):
        """High code quality ≠ authorization for hunting."""
        readme = """
        # Well-Built Protocol

        State-of-the-art smart contract implementation.

        - Comprehensive test suite
        - Battle-tested implementation
        - Advanced access control
        - Complex state transitions

        This protocol does not have a bug bounty program.
        """

        result = self.detector.classify_authorization(
            repo_owner="quality-org",
            repo_name="well-built",
            readme_content=readme,
            description="Production-grade DeFi protocol",
        )

        # Could have technical interest, but no authorization
        self.assertEqual(result.state, crawler_strict.AuthorizationState.UNCONFIRMED)
        self.assertFalse(result.is_authorized())
        self.assertEqual(result.authorization_confidence, 0.0)
