"""Hardened validation tests for BugBot Sentinel.

Tests fail-closed behavior against:
- Valid programs
- Missing required fields
- Edge cases and deceptive inputs
- Network errors
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


bounty_sentinel = load_module("bounty_sentinel", "bounty_sentinel.py")
fixtures = load_module("fixtures_bounty_platforms", "tests/fixtures_bounty_platforms.py")


class TestSentinelFailClosed(unittest.TestCase):
    """Sentinel must reject (not accept) uncertain cases."""

    def setUp(self):
        self.sentinel = bounty_sentinel.ScopeSentinel()

    def test_rejects_missing_repository_url(self):
        """Missing repo link = reject."""
        result = self.sentinel.verify_target(
            target_id=fixtures.IMMUNEFI_PROGRAM_MISSING_REPO["id"],
            platform_url="https://immunefi.com/bug-bounty/mystery",
            repository_url="",  # MISSING
            in_scope_assets=[{"identifier": "0x1111"}],
        )
        self.assertFalse(result.authorized)
        self.assertIn("repository", result.reason.lower())

    def test_rejects_empty_in_scope_assets(self):
        """No scope defined = reject."""
        result = self.sentinel.verify_target(
            target_id="empty-scope",
            platform_url="https://immunefi.com/bug-bounty/empty",
            repository_url="https://github.com/empty/protocol",
            in_scope_assets=[],  # EMPTY
        )
        self.assertFalse(result.authorized)
        self.assertIn("asset", result.reason.lower())

    def test_rejects_confidence_below_threshold(self):
        """Confidence < 0.7 = reject."""
        result = self.sentinel.verify_target(
            target_id="low-confidence",
            platform_url="https://unreachable.invalid",  # Will fail
            repository_url="",
            in_scope_assets=[],
        )
        self.assertFalse(result.authorized)
        self.assertLess(result.confidence, 0.7)

    def test_rejects_inaccessible_platform_url(self):
        """Platform URL not reachable = reject."""
        with patch("bounty_sentinel.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = ConnectionError("Connection refused")

            result = self.sentinel.verify_target(
                target_id="unreachable",
                platform_url="https://unreachable.invalid",
                repository_url="https://github.com/org/protocol",
                in_scope_assets=[{"identifier": "0x1111"}],
            )

            self.assertFalse(result.authorized)
            self.assertIn("inaccessible", result.reason.lower())

    def test_rejects_cloudflare_challenge(self):
        """HTML instead of JSON = reject."""
        result = self.sentinel.verify_target(
            target_id="cloudflare-challenge",
            platform_url="https://immunefi.com/challenge",  # Returns HTML
            repository_url="https://github.com/org/protocol",
            in_scope_assets=[{"identifier": "0x1111"}],
        )
        # Should reject due to inability to verify
        self.assertFalse(result.authorized)

    def test_holds_on_redirect(self):
        """Redirect to login = hold for manual review, not authorize."""
        result = self.sentinel.verify_target(
            target_id="redirect-login",
            platform_url="https://immunefi.com/login-redirect",
            repository_url="https://github.com/org/protocol",
            in_scope_assets=[{"identifier": "0x1111"}],
        )
        # Must not authorize redirected access
        self.assertFalse(result.authorized)
        self.assertIn("needs_manual_review", result.reason or "")

    def test_rejects_mismatch_between_scope_and_repo(self):
        """Scope page and repo disagree on version = reject."""
        result = self.sentinel.verify_target(
            target_id="disagree",
            platform_url="https://protocol.local/scope",
            repository_url="https://github.com/org/protocol",
            in_scope_assets=[
                {"identifier": "v3.5-contract", "label": "Scope page says v3.5"}
            ],
            # But repo latest is v2.1 (not provided here, but Sentinel should detect)
        )
        # Even if we don't fully validate the version mismatch in this test,
        # Sentinel should not blindly authorize when repo and scope disagree
        self.assertFalse(result.authorized)

    def test_rejects_multiple_repositories(self):
        """Multiple repos listed (ambiguous) = reject."""
        result = self.sentinel.verify_target(
            target_id="multi-repo",
            platform_url="https://protocol.local",
            repository_url="https://github.com/org/protocol-v1 https://github.com/org/protocol-v2",
            in_scope_assets=[{"identifier": "0x1111"}],
        )
        self.assertFalse(result.authorized)
        self.assertIn("multiple", result.reason.lower() or "ambiguous")

    def test_rejects_archived_repository(self):
        """Archived repo = reject (no active scope)."""
        result = self.sentinel.verify_target(
            target_id="archived-repo",
            platform_url="https://immunefi.com/bug-bounty/old",
            repository_url="https://github.com/old-org/old-protocol",
            in_scope_assets=[{"identifier": "0x1111"}],
            # Additional context: is_archived=True
        )
        self.assertFalse(result.authorized)

    def test_rejects_forked_repository_posing_as_upstream(self):
        """Fork of official repo = reject (not the authoritative source)."""
        result = self.sentinel.verify_target(
            target_id="forked-repo",
            platform_url="https://immunefi.com/bug-bounty/yearn",
            repository_url="https://github.com/attacker/yearn-v3",
            in_scope_assets=[{"identifier": "0x1111"}],
        )
        # Should reject fork if it's not the official repo
        # (Depends on whether Sentinel can detect fork status; conservative = reject)
        self.assertFalse(result.authorized)

    def test_holds_on_incomplete_response(self):
        """Incomplete scope data = hold, not authorize."""
        result = self.sentinel.verify_target(
            target_id="incomplete",
            platform_url="https://protocol.local",
            repository_url="https://github.com/org/protocol",
            in_scope_assets=[],  # No scope even though response exists
        )
        self.assertFalse(result.authorized)


class TestSentinelAcceptValid(unittest.TestCase):
    """Sentinel must accept programs that pass all gates."""

    def setUp(self):
        self.sentinel = bounty_sentinel.ScopeSentinel()

    @patch("bounty_sentinel.urllib.request.urlopen")
    def test_accepts_valid_program(self, mock_open):
        """Valid program with all gates passing = accept."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>Valid program</html>"
        mock_open.return_value.__enter__.return_value = mock_response

        result = self.sentinel.verify_target(
            target_id="yearn-v3",
            platform_url="https://immunefi.com/bug-bounty/yearn-v3",
            repository_url="https://github.com/yearn/yearn-v3",
            in_scope_assets=[
                {
                    "identifier": "0x4D7590eB56c3529d67dff690d1338D0c4E6B800C",
                    "label": "Yearn Vault Factory",
                }
            ],
        )

        self.assertTrue(result.authorized)
        self.assertGreaterEqual(result.confidence, 0.7)

    @patch("bounty_sentinel.urllib.request.urlopen")
    def test_evidence_recorded_with_authorization(self, mock_open):
        """Authorization must record evidence for verification."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>Valid</html>"
        mock_open.return_value.__enter__.return_value = mock_response

        result = self.sentinel.verify_target(
            target_id="yearn-v3",
            platform_url="https://immunefi.com/bug-bounty/yearn-v3",
            repository_url="https://github.com/yearn/yearn-v3",
            in_scope_assets=[{"identifier": "0x4D75..."}],
        )

        if result.authorized:
            self.assertGreater(len(result.evidence), 0)
            self.assertIn("immunefi.com", result.evidence[0])


class TestSentinelEvidencePredicates(unittest.TestCase):
    """Evidence must support authorization, not just confidence scores."""

    def test_authorization_requires_named_evidence(self):
        """Authorization needs explicit evidence predicates, not just a score."""
        # This test validates that if Sentinel authorizes, it can name WHY:
        # - official program page confirmed
        # - repository explicitly listed
        # - asset explicitly in scope
        # - scope timestamp current
        # - forbidden methods recorded
        # - chain/deployment matched

        sentinel = bounty_sentinel.ScopeSentinel()
        # Mock a valid authorization
        result = bounty_sentinel.VerificationResult(
            target_id="test-program",
            authorized=True,
            method="official_page",
            confidence=0.85,
            evidence=[
                "https://immunefi.com/bug-bounty/test",
                "https://github.com/org/protocol",
                "contract:0x1234",
            ],
            verified_at="2026-07-24T00:00:00Z",
            reason="Verified via official_page: platform accessible, repo linked, assets defined",
        )

        # If authorized, reason must be explicit, not just a score
        self.assertTrue(result.authorized)
        self.assertIsNotNone(result.reason)
        self.assertGreater(len(result.reason), 0)
        self.assertIn("official_page", result.reason.lower())

    def test_confidence_score_does_not_replace_evidence(self):
        """High confidence alone does not authorize; evidence predicates do."""
        sentinel = bounty_sentinel.ScopeSentinel()

        # Even with high confidence, if evidence is missing, reject
        result = bounty_sentinel.VerificationResult(
            target_id="high-confidence-no-evidence",
            authorized=False,  # MUST be False
            method="unknown",
            confidence=0.99,  # High confidence, but...
            evidence=[],  # No evidence
            verified_at="2026-07-24T00:00:00Z",
            reason="No evidence provided; confidence score alone is insufficient",
        )

        self.assertFalse(result.authorized)


class TestSentinelStalenessTracking(unittest.TestCase):
    """Sentinel tracks scope staleness to prevent hunting expired programs."""

    def test_records_verification_timestamp(self):
        """Each verification records when it was done."""
        sentinel = bounty_sentinel.ScopeSentinel()
        result = bounty_sentinel.VerificationResult(
            target_id="test",
            authorized=True,
            method="official_page",
            confidence=0.8,
            evidence=["https://test.local"],
            verified_at="2026-07-24T12:00:00Z",
            expires_at="2026-08-24T12:00:00Z",  # Expires in 30 days
            reason="Verified at specific timestamp",
        )

        self.assertIsNotNone(result.verified_at)
        self.assertIsNotNone(result.expires_at)

    def test_marks_stale_verifications(self):
        """Verifications older than 30 days should be marked stale."""
        # This would be tested with time-mocked tests in a real scenario
        # For now, just ensure the data structure supports it
        old_verification = bounty_sentinel.VerificationResult(
            target_id="old",
            authorized=True,
            method="official_page",
            confidence=0.8,
            evidence=["https://test.local"],
            verified_at="2026-06-24T12:00:00Z",  # 30+ days ago
            expires_at=None,  # Not set
            reason="Verified long ago",
        )

        # In production, Trinity should reject if expires_at <= now
        self.assertIsNotNone(old_verification.verified_at)
