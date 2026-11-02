"""Finder regression and end-to-end tests; no external target interaction."""
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import github_discovery as finder


class FinderPipelineTests(unittest.TestCase):
    def test_json_collection_shapes(self):
        with patch.object(finder.urllib.request, 'urlopen', return_value=io.BytesIO(b'[{"name":"tests"}]')):
            self.assertEqual(finder.github_api_get_listing('/repos/a/b/contents'), [{'name': 'tests'}])
        with patch.object(finder.urllib.request, 'urlopen', return_value=io.BytesIO(b'[]')):
            with self.assertRaises(finder.GitHubAPIError):
                finder.github_api_get_json('/repos/a/b')
        with patch.object(finder.urllib.request, 'urlopen', return_value=io.BytesIO(b'[null]')):
            with self.assertRaises(finder.GitHubAPIError):
                finder.github_api_get_listing('/repos/a/b/contents')
        with patch.object(finder.urllib.request, 'urlopen', return_value=io.BytesIO(b'{}')):
            with self.assertRaises(finder.GitHubAPIError):
                finder.github_api_get_listing('/repos/a/b/contents')

    def test_missing_directory_differs_from_fetch_failure(self):
        with patch.object(finder, 'github_api_get_listing', side_effect=finder.GitHubAPIError('missing', status_code=404)):
            self.assertEqual(finder.list_repo_contents('a/b', '.github'), [])
        for error in (finder.GitHubAPIError('timeout'), finder.GitHubRateLimitError('rate limit')):
            with self.subTest(error=error), patch.object(finder, 'github_api_get_listing', side_effect=error):
                with self.assertRaises(finder.GitHubDiscoveryError):
                    finder.list_repo_contents('a/b')

    def test_timeout_and_429_without_rate_keyword(self):
        for error, expected in ((TimeoutError('timeout'), finder.GitHubAPIError),
                                (urllib.error.HTTPError('https://api.github.com', 429, 'busy', {}, io.BytesIO(b'busy')), finder.GitHubRateLimitError)):
            for client in (finder.github_api_get_json, finder.github_api_get_text):
                with self.subTest(client=client.__name__), patch.object(finder.urllib.request, 'urlopen', side_effect=error):
                    with self.assertRaises(expected):
                        client('/repos/a/b')

    def test_enrichment_failure_is_persisted_and_not_reported_absent(self):
        repo = {'full_name': 'a/b', 'html_url': 'https://github.com/a/b'}
        with patch.object(finder, 'search_repositories', return_value=[repo]), patch.object(finder, 'fetch_repo_details', return_value=repo), patch.object(finder, 'fetch_repo_readme', return_value='Security policy'), patch.object(finder, 'scan_public_signals', side_effect=finder.GitHubRateLimitError('quota exhausted')):
            bundle = finder.discover_repositories(['test'], token='dummy')
        candidate = bundle['candidates'][0]
        self.assertEqual(candidate['scan_status'], 'incomplete')
        self.assertEqual(bundle['summary']['incomplete'], 1)
        self.assertTrue(candidate['docs_present'])
        self.assertEqual(candidate['security_signals'], [])
        with tempfile.TemporaryDirectory() as tmp:
            run = finder.write_bundle(bundle, Path(tmp))
            self.assertIn('quota exhausted', (run / 'repos/a-b/summary.md').read_text())
            self.assertEqual(json.loads((run / 'bundle.json').read_text()), bundle)

    def test_renamed_repository_preserves_enrichment(self):
        original = {'full_name': 'old/name', 'html_url': 'https://github.com/old/name'}
        renamed = {'full_name': 'new/name', 'html_url': 'https://github.com/new/name'}
        with patch.object(finder, 'search_repositories', return_value=[original]), \
             patch.object(finder, 'fetch_repo_details', return_value=renamed), \
             patch.object(finder, 'fetch_repo_readme', return_value='Security policy') as readme_mock, \
             patch.object(finder, 'scan_public_signals', return_value={}) as signals_mock:
            bundle = finder.discover_repositories(['test'], token='dummy')
        readme_mock.assert_called_once_with('new/name', token='dummy')
        signals_mock.assert_called_once_with('new/name', 'Security policy', token='dummy')
        self.assertEqual(bundle['candidates'][0]['full_name'], 'new/name')
        self.assertEqual(bundle['candidates'][0]['scan_status'], 'complete')

    def test_score_cannot_upgrade_scope(self):
        candidate = finder.compute_repo_score(
            {'full_name': 'a/b', 'language': 'Solidity', 'topics': ['security', 'foundry'], 'open_issues_count': 10},
            'audit scope bug bounty foundry fuzz invariant access control oracle ' * 100,
            ['audit', 'scope', 'foundry'],
        )
        self.assertGreaterEqual(candidate.priority_score, 80)
        self.assertEqual(candidate.review_state, 'Needs scope confirmation')
        self.assertEqual(candidate.suggested_posture, 'Passive review only until scope is confirmed')

    def test_untouched_and_conflicting_decisions_fail_closed(self):
        template = finder.render_scope_confirmation_template({'full_name': 'a/b'}, {})
        for text in (template, '- `authorized`\n', 'reviewer_decision: authorized\nreviewer_decision: unclear\n'):
            self.assertEqual(finder.parse_scope_decision(text), 'unclear')

    def test_transport_through_plan_and_evidence_gate(self):
        """Exercise the real HTTP decoders and pipeline with GitHub-shaped fixtures."""
        repo = {'full_name': 'a/b', 'html_url': 'https://github.com/a/b', 'language': 'Solidity', 'open_issues_count': 2}
        payloads = {
            '/search/repositories': {'items': [repo]}, '/repos/a/b': repo,
            '/repos/a/b/readme': 'audit scope foundry invariant',
            '/repos/a/b/contents': [{'name': 'tests'}, {'name': 'SECURITY.md'}],
            '/repos/a/b/contents/.github': [],
            '/repos/a/b/contents/.github/workflows': [{'name': 'ci.yml', 'path': '.github/workflows/ci.yml'}],
            '/repos/a/b/contents/.github/workflows/ci.yml': 'run: forge test',
            '/repos/a/b/releases': [{'published_at': '2026-10-01T00:00:00Z'}],
        }
        def respond(request, timeout):
            from urllib.parse import urlparse
            data = payloads[urlparse(request.full_url).path]
            return io.BytesIO((data if isinstance(data, str) else json.dumps(data)).encode())
        with tempfile.TemporaryDirectory() as tmp, patch.object(finder.urllib.request, 'urlopen', side_effect=respond), patch.object(finder, 'get_github_token', return_value='dummy'):
            root = Path(tmp)
            bundle, run = finder.run_github_discovery(['solidity'], output_root=root)
            candidate = bundle['candidates'][0]
            self.assertEqual(candidate['scan_status'], 'complete')
            self.assertIn('Forge', candidate['workflow_tools'])
            self.assertIn('SECURITY.md present', candidate['security_signals'])
            self.assertEqual(candidate['authorization_state'], 'Public repo / no confirmed bounty scope')
            original = (run / 'bundle.json').read_bytes()
            selected = finder.copy_selection(candidate, run, run / 'selected')
            payload, _, _ = finder.run_selected_repo_hunt_plan('a/b', output_root=root)
            self.assertEqual(payload['scope_confirmation']['scope_status'], 'NOT AUTHORIZED')
            with self.assertRaises(finder.GitHubDiscoveryError):
                finder.require_authorized_scope(selected)
            evidence = root / 'policy.md'
            evidence.write_text('Synthetic policy fixture for a/b; analysis allowed.')
            confirmation = (Path(__file__).parent / 'fixtures/scope_confirmation_valid.md').read_text()
            expiry = (datetime.now(timezone.utc) + timedelta(days=365)).replace(microsecond=0).isoformat()
            confirmation = confirmation.replace('2027-06-30T12:00:00+00:00', expiry)
            confirmation = confirmation.replace('target_id: dvd-local-lab', 'target_id: a/b').replace('identity_status: local_fixture_unpinned', 'identity_status: verified_repo\ntarget_repo_url: https://github.com/a/b').replace('evidence_path: tests/fixtures/scope_evidence.md', f'evidence_path: {evidence}')
            scope_path = selected / 'scope_confirmation.md'
            scope_path.write_text(confirmation)
            self.assertEqual(finder.require_authorized_scope(selected)['scope_status'], 'AUTHORIZED')
            # The same confirmation feeds the operational BugBot gate.
            from bugbot.scope import issue_scope_grant_from_confirmation, require_authorized_scope
            grant_dir = root / 'grants'
            issued = issue_scope_grant_from_confirmation(scope_path, anchor_root=root, scope_dir=grant_dir)
            self.assertTrue(issued.success, issued.reason)
            with patch('bugbot.scope.default_scope_dir', return_value=grant_dir):
                grant = require_authorized_scope(action='analysis', target_id='a/b', target_ref='abc123def4567890abcdef1234567890abcdef12')
            self.assertEqual(grant.target_id, 'a/b')
            for before, after in (
                ('schema_version: 1.0', 'schema_version: 9.0'),
                ('schema_version: 1.0', 'schema_version: 1.0\nschema_version: 1.0'),
                ('target_ref: abc123def4567890abcdef1234567890abcdef12', 'target_ref: '),
                ('identity_status: verified_repo', 'identity_status: local_fixture_unpinned'),
                ('target_id: a/b', 'target_id: other/repo'),
                ('https://github.com/a/b', 'https://github.com/other/repo'),
                ('  - analysis', '  - planning'),
                (expiry, '2020-06-30T12:00:00+00:00'),
                ('2026-06-30T12:00:00+00:00', '2099-06-30T12:00:00+00:00'),
                (f'evidence_path: {evidence}', f'evidence_path: {root}/missing'),
            ):
                with self.subTest(change=before):
                    scope_path.write_text(confirmation.replace(before, after))
                    with self.assertRaises(finder.GitHubDiscoveryError):
                        finder.require_authorized_scope(selected)
            self.assertEqual((run / 'bundle.json').read_bytes(), original)
            self.assertTrue((selected / 'hunt_plan.md').is_file())

    def test_invalid_limits(self):
        for limit, per_query in ((0, 1), (1, 0), (101, 1), (1, 101)):
            with self.assertRaises(finder.GitHubDiscoveryError):
                finder.discover_repositories(limit=limit, per_query=per_query)

    def test_cli_exit_codes_distinguish_partial_and_denied(self):
        import anchor_cli
        from argparse import Namespace
        from contextlib import redirect_stdout
        args = Namespace(query=['test'], limit=1, per_query=1, include_forks=False, include_archived=False, no_readmes=False, output_root='/tmp/unused', json=True, repo='a/b', run_id='')
        with redirect_stdout(io.StringIO()), patch.object(anchor_cli, 'run_github_discovery', return_value=({'summary': {'incomplete': 1}}, Path('/tmp/unused'))):
            self.assertEqual(anchor_cli.cmd_github_crawl(args), 2)
            self.assertEqual(anchor_cli.cmd_github_profile_crawl(args, 'auth'), 2)
        for status, code in [('NOT AUTHORIZED', 1), ('AUTHORIZED', 0)]:
            with self.subTest(status=status), redirect_stdout(io.StringIO()), patch.object(anchor_cli, 'check_selected_repo_scope', return_value=(Path('/tmp/run'), Path('/tmp/selected'), {'scope_status': status})):
                self.assertEqual(anchor_cli.cmd_github_scope_check(args), code)
