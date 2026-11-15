"""Offline fail-closed tests; never contact HackerOne."""
import io
import unittest
import urllib.error
from unittest.mock import patch

from bounty_scout import AuthorizationStatus
from hackerone_readonly import HackerOneReadError, HackerOneReadOnly, _path, program_to_target


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.body = io.BytesIO(data)

    def read(self, size):
        return self.body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestHackerOneReadOnly(unittest.TestCase):
    def test_missing_credentials_fail_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(HackerOneReadError, "credentials missing"):
                HackerOneReadOnly()

    def test_allowlist_rejects_unapproved_paths(self):
        for kind, handle in [("reports", None), ("program", "../admin"),
                             ("program", "x?next=evil"), ("programs", "x")]:
            with self.subTest(kind=kind, handle=handle):
                with self.assertRaises(HackerOneReadError):
                    _path(kind, handle)
        self.assertEqual(_path("structured_scopes", "acme"),
                         "/v1/hackers/programs/acme/structured_scopes")

    def test_get_uses_only_official_https_get(self):
        class FakeOpener:
            def open(self, request, timeout):
                assert request.full_url == "https://api.hackerone.com/v1/hackers/programs"
                assert request.get_method() == "GET"
                assert timeout == 15
                return FakeResponse(b'{"data": []}')
        with patch("hackerone_readonly.urllib.request.build_opener", return_value=FakeOpener()):
            self.assertEqual(HackerOneReadOnly("user", "secret").get("programs"), {"data": []})

    def test_errors_never_reveal_secrets(self):
        class BadOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 401, "secret-value", {}, None)
        with patch("hackerone_readonly.urllib.request.build_opener", return_value=BadOpener()):
            with self.assertRaises(HackerOneReadError) as ctx:
                HackerOneReadOnly("user", "secret-value").get("programs")
        self.assertNotIn("secret-value", str(ctx.exception))

    def test_redirect_is_rejected(self):
        class RedirectOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 302, "moved",
                                             {"Location": "https://evil.test"}, None)
        with patch("hackerone_readonly.urllib.request.build_opener", return_value=RedirectOpener()):
            with self.assertRaisesRegex(HackerOneReadError, "redirect rejected"):
                HackerOneReadOnly("user", "secret").get("programs")

    def test_malformed_json_rejected(self):
        class BadJsonOpener:
            def open(self, request, timeout):
                return FakeResponse(b"not-json")
        with patch("hackerone_readonly.urllib.request.build_opener", return_value=BadJsonOpener()):
            with self.assertRaisesRegex(HackerOneReadError, "Malformed API JSON"):
                HackerOneReadOnly("user", "secret").get("programs")

    def test_import_cannot_authorize_scope(self):
        target = program_to_target({"type": "program", "attributes": {
            "handle": "acme", "name": "ACME", "open_scope": True,
            "submission_state": "open", "authorized": True,
            "structured_scopes": [{"asset": "*", "eligible_for_bounty": True}],
        }})
        self.assertEqual(target.authorization_status, AuthorizationStatus.SCOPE_UNVERIFIED)
        self.assertEqual(target.in_scope_assets, [])
        self.assertEqual(target.verified_at, "")

    def test_rate_limit_and_timeout_sanitized(self):
        cases = [(urllib.error.HTTPError("https://api.hackerone.com", 429, "secret", {}, None), "rate limited"),
                 (TimeoutError("secret"), "connection failed")]
        for exception, message in cases:
            class Broken:
                def open(self, request, timeout):
                    raise exception
            with patch("hackerone_readonly.urllib.request.build_opener", return_value=Broken()):
                with self.assertRaisesRegex(HackerOneReadError, message) as ctx:
                    HackerOneReadOnly("user", "secret").get("programs")
                self.assertNotIn("secret", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
