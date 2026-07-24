"""Tests for bounty crawler module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase
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


bounty_crawler = load_module("bounty_crawler", "bounty_crawler.py")


class TestBugSignalExtractor(TestCase):
    def test_extract_signals_detects_reentrancy(self):
        title = "Potential reentrancy in withdraw function"
        body = "External call occurs before state update"
        signals = bounty_crawler.BugSignalExtractor.extract_signals(title, body)

        self.assertIn("reentrancy", signals["categories"])
        self.assertGreater(signals["score"], 0)

    def test_extract_signals_detects_access_control(self):
        title = "Missing access control check"
        body = "The admin function lacks permission verification"
        signals = bounty_crawler.BugSignalExtractor.extract_signals(title, body)

        self.assertIn("access_control", signals["categories"])

    def test_is_relevant_returns_true_for_multiple_signals(self):
        issue = bounty_crawler.GitHubIssue(
            repo=bounty_crawler.GitHubRepo(
                owner="test",
                name="repo",
                url="https://github.com/test/repo",
            ),
            number=1,
            title="Missing access control and unchecked overflow",
            body="Critical reentrancy issue in external calls",
            author="user",
            created_at="2026-01-01T00:00:00Z",
            url="https://github.com/test/repo/issues/1",
        )

        self.assertTrue(bounty_crawler.BugSignalExtractor.is_relevant(issue))

    def test_is_relevant_returns_false_for_low_score(self):
        issue = bounty_crawler.GitHubIssue(
            repo=bounty_crawler.GitHubRepo(
                owner="test",
                name="repo",
                url="https://github.com/test/repo",
            ),
            number=1,
            title="Minor typo in comments",
            body="There's a spelling error in the code comments",
            author="user",
            created_at="2026-01-01T00:00:00Z",
            url="https://github.com/test/repo/issues/1",
        )

        self.assertFalse(bounty_crawler.BugSignalExtractor.is_relevant(issue))

    def test_severity_detection_critical(self):
        signals = bounty_crawler.BugSignalExtractor.extract_signals(
            "Critical: Lost funds vulnerability",
            "Funds are stolen due to unchecked external call",
        )
        self.assertEqual(signals["severity"], "critical")

    def test_severity_detection_high(self):
        signals = bounty_crawler.BugSignalExtractor.extract_signals(
            "High: Missing authorization",
            "Significant permission bypass",
        )
        self.assertEqual(signals["severity"], "high")


class TestGitHubClient(TestCase):
    def setUp(self):
        self.client = bounty_crawler.GitHubClient(token="test_token")

    @patch("bounty_crawler.urllib.request.urlopen")
    def test_search_repos_parses_response(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "items": [
                    {
                        "owner": {"login": "test"},
                        "name": "repo1",
                        "html_url": "https://github.com/test/repo1",
                        "description": "A test repo",
                        "stargazers_count": 100,
                        "language": "Solidity",
                        "topics": ["security"],
                    }
                ]
            }
        ).encode("utf-8")
        mock_response.headers = {
            "X-RateLimit-Remaining": "59",
            "X-RateLimit-Reset": "1000000000",
        }
        mock_urlopen.return_value.__enter__.return_value = mock_response

        repos = self.client.search_repos("security", limit=1)

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0].owner, "test")
        self.assertEqual(repos[0].name, "repo1")
        self.assertEqual(repos[0].stars, 100)

    @patch("bounty_crawler.urllib.request.urlopen")
    def test_get_issues_parses_response(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            [
                {
                    "number": 123,
                    "title": "Security Issue",
                    "body": "Potential vulnerability",
                    "user": {"login": "user1"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "html_url": "https://github.com/test/repo/issues/123",
                    "labels": [{"name": "security"}, {"name": "critical"}],
                }
            ]
        ).encode("utf-8")
        mock_response.headers = {
            "X-RateLimit-Remaining": "59",
            "X-RateLimit-Reset": "1000000000",
        }
        mock_urlopen.return_value.__enter__.return_value = mock_response

        issues = self.client.get_issues("test", "repo", limit=1)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].number, 123)
        self.assertEqual(issues[0].title, "Security Issue")
        self.assertIn("security", issues[0].labels)


class TestCreateLeadFromIssue(TestCase):
    def test_creates_valid_lead_record(self):
        issue = bounty_crawler.GitHubIssue(
            repo=bounty_crawler.GitHubRepo(
                owner="solana",
                name="anchor",
                url="https://github.com/solana/anchor",
            ),
            number=1234,
            title="Missing access control in admin function",
            body="The upgrade function lacks permission checks",
            author="security_researcher",
            created_at="2026-01-01T00:00:00Z",
            url="https://github.com/solana/anchor/issues/1234",
        )

        lead = bounty_crawler.create_lead_from_issue(issue, profile="auth")

        self.assertEqual(lead.state, "signal")
        self.assertEqual(lead.target, "solana/anchor")
        self.assertEqual(lead.scope_status, "unknown")
        self.assertIn("Missing access control", lead.claim)
        self.assertIn(issue.url, lead.evidence_refs)
        self.assertGreater(len(lead.repro_plan), 0)

    def test_lead_has_required_trinity_fields(self):
        issue = bounty_crawler.GitHubIssue(
            repo=bounty_crawler.GitHubRepo(
                owner="test",
                name="repo",
                url="https://github.com/test/repo",
            ),
            number=1,
            title="Test issue",
            body="Test body",
            author="user",
            created_at="2026-01-01T00:00:00Z",
            url="https://github.com/test/repo/issues/1",
        )

        lead = bounty_crawler.create_lead_from_issue(issue)

        # Required Trinity fields
        self.assertIsNotNone(lead.lead_id)
        self.assertIsNotNone(lead.target)
        self.assertIsNotNone(lead.title)
        self.assertIsNotNone(lead.state)
        self.assertIsNotNone(lead.created_at)
        self.assertIsNotNone(lead.updated_at)


class TestBountyCrawler(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.crawler = bounty_crawler.BountyCrawler(
            token="test_token",
            output_dir=self.output_dir,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generate_leads_creates_leads_from_issues(self):
        issues = [
            bounty_crawler.GitHubIssue(
                repo=bounty_crawler.GitHubRepo(
                    owner="test",
                    name="repo",
                    url="https://github.com/test/repo",
                ),
                number=i,
                title=f"Issue {i}: Access control issue",
                body="Missing permission check",
                author="user",
                created_at="2026-01-01T00:00:00Z",
                url=f"https://github.com/test/repo/issues/{i}",
            )
            for i in range(1, 4)
        ]

        leads = self.crawler.generate_leads(issues)

        self.assertEqual(len(leads), 3)
        for lead in leads:
            self.assertEqual(lead.state, "signal")
            self.assertEqual(lead.target, "test/repo")

    def test_save_leads_writes_jsonl_file(self):
        issues = [
            bounty_crawler.GitHubIssue(
                repo=bounty_crawler.GitHubRepo(
                    owner="test",
                    name="repo",
                    url="https://github.com/test/repo",
                ),
                number=1,
                title="Test issue",
                body="Test",
                author="user",
                created_at="2026-01-01T00:00:00Z",
                url="https://github.com/test/repo/issues/1",
            )
        ]

        leads = self.crawler.generate_leads(issues)
        output_path = self.crawler.save_leads(leads, output_file="test.jsonl")

        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            line = f.readline()
            data = json.loads(line)
            self.assertEqual(data["state"], "signal")
            self.assertEqual(data["target"], "test/repo")

    def test_save_leads_creates_output_directory(self):
        nonexistent_dir = self.output_dir / "subdir" / "nested"
        crawler = bounty_crawler.BountyCrawler(output_dir=nonexistent_dir)

        self.assertTrue(nonexistent_dir.exists())
