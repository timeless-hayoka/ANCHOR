from __future__ import annotations

import importlib.util
import io
import json
import sys
from email.message import Message
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


github_discovery = load_module("github_discovery", "github_discovery.py")


class GitHubDiscoveryTests(TestCase):
    def test_rate_limit_response_is_classified(self):
        headers = Message()
        headers["X-RateLimit-Reset"] = "1710000000"
        headers["Retry-After"] = "30"
        error = urllib.error.HTTPError(
            "https://api.github.com/search/repositories?q=test",
            403,
            "Forbidden",
            headers,
            io.BytesIO(b'{"message":"API rate limit exceeded"}'),
        )

        with patch.object(urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(github_discovery.GitHubRateLimitError) as excinfo:
                github_discovery.github_api_get_json("/search/repositories?q=test")

        self.assertEqual(excinfo.exception.reset_at, "1710000000")
        self.assertEqual(excinfo.exception.retry_after, 30)

    def test_private_or_archived_repo_is_skipped_cleanly(self):
        candidate = github_discovery.compute_repo_score(
            {
                "full_name": "owner/archived-repo",
                "html_url": "https://github.com/owner/archived-repo",
                "description": "Archived repo",
                "stargazers_count": 1,
                "forks_count": 0,
                "open_issues_count": 0,
                "pushed_at": "2020-01-01T00:00:00Z",
                "updated_at": "2020-01-01T00:00:00Z",
                "archived": True,
                "fork": False,
                "language": "Python",
                "topics": [],
            },
            "",
            ["archived"],
            public_signals={"authorization_state": "Public repo / no confirmed bounty scope"},
        )
        self.assertTrue(candidate.archived)
        self.assertEqual(candidate.recommendation, "skip")

    def test_missing_readme_and_workflows_are_handled(self):
        with patch.object(github_discovery, "list_repo_contents", return_value=[]), patch.object(github_discovery, "read_repo_file", return_value=""), patch.object(github_discovery, "github_api_get_json", return_value=[]):
            signals = github_discovery.scan_public_signals("owner/project", "", token="dummy")
        self.assertIn("SECURITY.md absent", signals["security_signals"][0])
        self.assertEqual(signals["workflow_tools"], [])
        self.assertEqual(signals["dependency_manifests"], [])

    def test_malformed_api_payload_raises_clean_error(self):
        with patch.object(urllib.request, "urlopen", return_value=io.BytesIO(b"[]")):
            with self.assertRaises(github_discovery.GitHubAPIError):
                github_discovery.github_api_get_json("/repos/owner/project")

    def test_duplicate_repos_across_queries_are_deduplicated(self):
        with patch.object(github_discovery, "search_repositories", side_effect=[
            [{"full_name": "owner/repo", "stargazers_count": 10, "forks_count": 1, "open_issues_count": 2, "html_url": "https://github.com/owner/repo"}],
            [{"full_name": "owner/repo", "stargazers_count": 12, "forks_count": 1, "open_issues_count": 2, "html_url": "https://github.com/owner/repo"}],
        ]), patch.object(github_discovery, "fetch_repo_details", return_value={
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
            "description": "Repo",
            "stargazers_count": 12,
            "forks_count": 1,
            "open_issues_count": 2,
            "pushed_at": "2026-06-29T00:00:00Z",
            "updated_at": "2026-06-29T00:00:00Z",
            "archived": False,
            "fork": False,
            "language": "Python",
            "topics": ["testing"],
        }), patch.object(github_discovery, "fetch_repo_readme", return_value="README"), patch.object(github_discovery, "scan_public_signals", return_value={
            "security_paths": [],
            "workflow_names": [],
            "workflow_tools": [],
            "workflow_signals": [],
            "dependency_manifests": [],
            "likely_surface": ["tests / fuzzing / CI"],
            "security_signals": ["SECURITY.md absent"],
            "release_cadence": "active",
            "authorization_state": "Public repo / no confirmed bounty scope",
            "review_state": "Needs scope confirmation",
            "suggested_posture": "Passive review only until scope is confirmed",
            "audit_mentions": False,
            "evidence_sources": [],
        }):
            bundle = github_discovery.discover_repositories(["query one", "query two"], limit=10, per_query=5, fetch_readmes=True, token="dummy")

        self.assertEqual(len(bundle["candidates"]), 1)
        self.assertEqual(bundle["candidates"][0]["full_name"], "owner/repo")

    def test_network_timeout_is_reported_cleanly(self):
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("timed out")):
            with self.assertRaises(github_discovery.GitHubAPIError):
                github_discovery.github_api_get_text("/repos/owner/project/readme")

    def test_authorization_posture_classification(self):
        with patch.object(github_discovery, "list_repo_contents", return_value=[{"name": "README.md"}]), patch.object(github_discovery, "read_repo_file", return_value="Bug bounty scope and security policy"), patch.object(github_discovery, "github_api_get_json", return_value=[]):
            signals = github_discovery.scan_public_signals("owner/project", "Bug bounty scope and security policy", token="dummy")

        self.assertEqual(signals["authorization_state"], "Explicitly authorized bounty / audit scope")
        self.assertEqual(signals["suggested_posture"], "Local clone analysis allowed and scope-limited review is encouraged")

    def test_scoring_rewards_security_context_and_testing_depth(self):
        candidate = github_discovery.compute_repo_score(
            {
                "full_name": "owner/security-lab",
                "html_url": "https://github.com/owner/security-lab",
                "description": "Smart contract security lab with fuzzing and invariants",
                "stargazers_count": 42,
                "forks_count": 8,
                "open_issues_count": 4,
                "pushed_at": "2026-06-29T00:00:00Z",
                "updated_at": "2026-06-29T00:00:00Z",
                "archived": False,
                "fork": False,
                "language": "Solidity",
                "topics": ["solidity", "foundry", "fuzzing", "security"],
            },
            "Security policy, bug bounty scope, access control, upgradeability, external calls, invariant tests, echidna, codeql, semgrep, slither, foundry.toml",
            ["security", "fuzzing", "invariant", "access", "control"],
            public_signals={
                "authorization_state": "Explicitly authorized bounty / audit scope",
                "review_state": "Needs scope confirmation",
                "suggested_posture": "Passive review only until scope is confirmed",
                "likely_surface": ["smart-contract logic", "access control", "upgradeability", "external calls", "tests / fuzzing / CI"],
                "security_signals": [
                    "SECURITY.md present",
                    "CodeQL present",
                    "Semgrep present",
                    "Slither present",
                    "tests/fuzzing present",
                    "audit/advisory language present",
                ],
                "workflow_tools": ["CodeQL", "Semgrep", "Slither", "Foundry", "Echidna"],
                "dependency_manifests": ["foundry.toml"],
                "release_cadence": "active",
                "evidence_sources": [],
            },
        )

        self.assertGreaterEqual(candidate.priority_score, 80)
        self.assertEqual(candidate.recommendation, "join")
        self.assertIn("security policy is visible", candidate.reasons)
        self.assertIn("test or fuzz workflow is present", candidate.reasons)
        self.assertIn("smart-contract surface is explicit", candidate.reasons)
        self.assertIn("access control surface is explicit", candidate.reasons)

    def test_profile_scoring_biases_matching_bug_classes(self):
        cases = [
            (
                "auth",
                {
                    "full_name": "owner/auth-lab",
                    "html_url": "https://github.com/owner/auth-lab",
                    "description": "Access control study",
                    "stargazers_count": 5,
                    "forks_count": 1,
                    "open_issues_count": 2,
                    "pushed_at": "2026-06-29T00:00:00Z",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "archived": False,
                    "fork": False,
                    "language": "Solidity",
                    "topics": ["security", "solidity"],
                },
                "access control, owner, role, authorization",
                "authorization boundary review",
            ),
            (
                "upgrade",
                {
                    "full_name": "owner/upgrade-lab",
                    "html_url": "https://github.com/owner/upgrade-lab",
                    "description": "Proxy upgrade study",
                    "stargazers_count": 5,
                    "forks_count": 1,
                    "open_issues_count": 2,
                    "pushed_at": "2026-06-29T00:00:00Z",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "archived": False,
                    "fork": False,
                    "language": "Solidity",
                    "topics": ["security", "solidity"],
                },
                "proxy, initializer, implementation, uups",
                "upgrade and initializer review",
            ),
            (
                "accounting",
                {
                    "full_name": "owner/accounting-lab",
                    "html_url": "https://github.com/owner/accounting-lab",
                    "description": "Accounting drift study",
                    "stargazers_count": 5,
                    "forks_count": 1,
                    "open_issues_count": 2,
                    "pushed_at": "2026-06-29T00:00:00Z",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "archived": False,
                    "fork": False,
                    "language": "Solidity",
                    "topics": ["security", "solidity"],
                },
                "balance, share, rounding, dust, precision",
                "accounting drift review",
            ),
            (
                "oracle",
                {
                    "full_name": "owner/oracle-lab",
                    "html_url": "https://github.com/owner/oracle-lab",
                    "description": "Oracle validation study",
                    "stargazers_count": 5,
                    "forks_count": 1,
                    "open_issues_count": 2,
                    "pushed_at": "2026-06-29T00:00:00Z",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "archived": False,
                    "fork": False,
                    "language": "Solidity",
                    "topics": ["security", "solidity"],
                },
                "oracle, stale price feed, input validation",
                "oracle delay review",
            ),
            (
                "external",
                {
                    "full_name": "owner/external-lab",
                    "html_url": "https://github.com/owner/external-lab",
                    "description": "External call study",
                    "stargazers_count": 5,
                    "forks_count": 1,
                    "open_issues_count": 2,
                    "pushed_at": "2026-06-29T00:00:00Z",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "archived": False,
                    "fork": False,
                    "language": "Solidity",
                    "topics": ["security", "solidity"],
                },
                "delegatecall, callback, reentrancy, external call",
                "external call ordering review",
            ),
        ]

        for profile, repo, readme, expected_reason in cases:
            candidate = github_discovery.compute_repo_score(
                repo,
                readme,
                [profile, "security"],
                public_signals={
                    "authorization_state": "Public repo / no confirmed bounty scope",
                    "review_state": "Needs scope confirmation",
                    "suggested_posture": "Passive review only until scope is confirmed",
                    "likely_surface": ["smart-contract logic"],
                    "security_signals": ["SECURITY.md present", "tests/fuzzing present"],
                    "workflow_tools": ["Foundry", "Echidna"],
                    "dependency_manifests": ["foundry.toml"],
                    "release_cadence": "active",
                    "evidence_sources": [],
                },
                profile=profile,
            )
            self.assertGreaterEqual(candidate.priority_score, 80)
            self.assertIn(f"{profile} crawler profile match", candidate.reasons)
            self.assertIn(expected_reason, candidate.reasons)

    def test_selection_copies_candidate_without_mutating_source_bundle(self):
        run_dir = Path(self._tmpdir())
        run_dir.mkdir(parents=True, exist_ok=True)
        bundle = {
            "generated_at": "2026-06-29T00:00:00+00:00",
            "queries": ["solidity fuzzing"],
            "candidates": [
                {
                    "full_name": "perimetersec/fuzzlib",
                    "html_url": "https://github.com/perimetersec/fuzzlib",
                    "description": "General purpose unopinionated Solidity fuzzing library",
                    "stars": 60,
                    "forks": 15,
                    "open_issues": 10,
                    "pushed_at": "2026-01-18T13:53:53Z",
                    "updated_at": "2026-04-15T08:53:52Z",
                    "archived": False,
                    "fork": False,
                    "language": "Solidity",
                    "topics": ["echidna", "foundry", "fuzzing", "solidity"],
                    "docs_present": True,
                    "readme_excerpt": "# Fuzzlib",
                    "priority_score": 100,
                    "authorization_state": "Explicitly authorized bounty / audit scope",
                    "review_state": "Explicitly authorized bounty / audit scope",
                    "suggested_posture": "Local clone analysis allowed and scope-limited review is encouraged",
                    "likely_surface": ["smart-contract logic", "tests / fuzzing / CI"],
                    "security_signals": ["audit/advisory language present"],
                    "dependency_manifests": [],
                    "workflow_tools": [],
                    "release_cadence": "inactive",
                    "evidence_sources": [],
                    "score": 20,
                    "recommendation": "join",
                    "reasons": ["repo is not archived"],
                    "signals": [],
                    "query_matches": ["fuzzing"],
                    "issue_angles": ["testing/invariants", "docs/workflow clarity", "regression harness or machine-readable output"],
                },
            ],
        }
        (run_dir / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
        (run_dir / "summary.md").write_text("summary", encoding="utf-8")
        (run_dir / "repos").mkdir(parents=True, exist_ok=True)
        (run_dir / "repos" / "perimetersec-fuzzlib").mkdir(parents=True, exist_ok=True)
        (run_dir / "repos" / "perimetersec-fuzzlib" / "candidate.json").write_text(json.dumps(bundle["candidates"][0]), encoding="utf-8")
        (run_dir / "repos" / "perimetersec-fuzzlib" / "summary.md").write_text("summary", encoding="utf-8")

        selected_dir = github_discovery.copy_selection(bundle["candidates"][0], run_dir, run_dir / "selected")

        self.assertTrue((run_dir / "repos" / "perimetersec-fuzzlib" / "candidate.json").exists())
        self.assertTrue((selected_dir / "candidate.json").exists())
        self.assertTrue((selected_dir / "summary.md").exists())
        selection = json.loads((selected_dir / "selection.json").read_text(encoding="utf-8"))
        self.assertEqual(selection["repo"], "perimetersec/fuzzlib")
        self.assertEqual(selection["selection_status"], "human_approved")
        self.assertEqual(selection["authorization_state"], "scope_confirmation_required")
        self.assertEqual(selection["next_action"], "Review published scope and repository security policy before local analysis.")

    def test_selected_repo_hunt_plan_is_written_next_to_selection(self):
        output_root = Path(self._tmpdir())
        run_dir = output_root / "2026-06-29t00-00-00-00-00"
        selected_dir = run_dir / "selected" / "perimetersec-fuzzlib"
        selected_dir.mkdir(parents=True, exist_ok=True)
        candidate = {
            "full_name": "perimetersec/fuzzlib",
            "html_url": "https://github.com/perimetersec/fuzzlib",
            "description": "General purpose unopinionated Solidity fuzzing library",
            "stars": 60,
            "forks": 15,
            "open_issues": 10,
            "pushed_at": "2026-01-18T13:53:53Z",
            "updated_at": "2026-04-15T08:53:52Z",
            "archived": False,
            "fork": False,
            "language": "Solidity",
            "topics": ["echidna", "foundry", "fuzzing", "solidity"],
            "docs_present": True,
            "readme_excerpt": "# Fuzzlib",
            "priority_score": 100,
            "authorization_state": "Explicitly authorized bounty / audit scope",
            "review_state": "Explicitly authorized bounty / audit scope",
            "suggested_posture": "Local clone analysis allowed and scope-limited review is encouraged",
            "likely_surface": ["smart-contract logic", "tests / fuzzing / CI"],
            "security_signals": ["audit/advisory language present"],
            "dependency_manifests": [],
            "workflow_tools": [],
            "release_cadence": "inactive",
            "evidence_sources": [],
            "score": 20,
            "recommendation": "join",
            "reasons": ["repo is not archived"],
            "signals": [],
            "query_matches": ["fuzzing"],
            "issue_angles": ["testing/invariants", "docs/workflow clarity", "regression harness or machine-readable output"],
        }
        selection = {
            "schema_version": "1.0",
            "repo": "perimetersec/fuzzlib",
            "selected_from_run": run_dir.name,
            "selected_at": "2026-06-29T00:00:00+00:00",
            "selection_status": "human_approved",
            "authorization_state": "scope_confirmation_required",
            "next_action": "Review published scope and repository security policy before local analysis.",
        }
        (selected_dir / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
        (selected_dir / "summary.md").write_text("summary", encoding="utf-8")
        (selected_dir / "selection.json").write_text(json.dumps(selection), encoding="utf-8")

        payload, resolved_run_dir, resolved_selected_dir = github_discovery.run_selected_repo_hunt_plan(
            "perimetersec/fuzzlib",
            output_root=output_root,
            run_id=run_dir.name,
        )

        self.assertEqual(payload["selection"]["repo"], "perimetersec/fuzzlib")
        self.assertEqual(payload["selection"]["selection_status"], "human_approved")
        self.assertIn("published scope", payload["next_actions"][0].lower())
        self.assertEqual(resolved_run_dir.name, run_dir.name)
        self.assertEqual(resolved_selected_dir, selected_dir)
        scope_md = (selected_dir / "scope_confirmation.md").read_text(encoding="utf-8")
        self.assertIn("Scope Confirmation", scope_md)
        self.assertIn("reviewer_decision:", scope_md)
        self.assertIn("Source URL:", scope_md)
        self.assertIn("In-scope assets / commit", scope_md)
        self.assertIn("Permitted testing methods", scope_md)
        self.assertIn("Prohibited actions", scope_md)
        self.assertIn("Disclosure / reporting channel", scope_md)
        self.assertIn("Date checked", scope_md)
        self.assertIn("Reviewer decision", scope_md)
        plan_md = (selected_dir / "hunt_plan.md").read_text(encoding="utf-8")
        self.assertIn("Selected Repo Hunt Plan", plan_md)
        self.assertIn("Source run:", plan_md)
        self.assertIn("Authorization state: scope_confirmation_required", plan_md)
        self.assertIn("Public evidence reviewed", plan_md)
        self.assertIn("Likely code/security surfaces", plan_md)
        self.assertIn("Explicitly excluded until scope confirmation", plan_md)
        self.assertIn("Smallest safe next action", plan_md)
        self.assertIn("Stop conditions", plan_md)
        self.assertIn("Evidence needed before local analysis is allowed", plan_md)
        self.assertNotIn("Hypothesis templates", plan_md)
        self.assertTrue((selected_dir / "hunt_plan.json").exists())
        self.assertTrue((selected_dir / "hunt_plan.md").exists())

    def test_scope_confirmation_requires_authorized_decision(self):
        selected_dir = Path(self._tmpdir()) / "selected" / "perimetersec-fuzzlib"
        selected_dir.mkdir(parents=True, exist_ok=True)
        (selected_dir / "scope_confirmation.md").write_text(
            "# Scope Confirmation\n\n"
            "reviewer_decision: unclear\n",
            encoding="utf-8",
        )

        scope = github_discovery.evaluate_scope_confirmation(selected_dir)
        self.assertEqual(scope["scope_status"], "NOT AUTHORIZED")
        self.assertEqual(scope["reason"], "reviewer_decision is unclear")
        self.assertEqual(scope["allowed_actions"], "planning only")

        with self.assertRaises(github_discovery.GitHubDiscoveryError) as excinfo:
            github_discovery.require_authorized_scope(selected_dir)
        self.assertIn("Scope status: NOT AUTHORIZED", str(excinfo.exception))
        self.assertIn("Allowed actions: planning only", str(excinfo.exception))

        (selected_dir / "scope_confirmation.md").write_text(
            "# Scope Confirmation\n\n"
            "reviewer_decision: authorized\n",
            encoding="utf-8",
        )
        scope = github_discovery.evaluate_scope_confirmation(selected_dir)
        self.assertEqual(scope["scope_status"], "AUTHORIZED")
        self.assertEqual(scope["allowed_actions"], "planning and authorized analysis")

    def _tmpdir(self):
        import tempfile
        return tempfile.mkdtemp()
