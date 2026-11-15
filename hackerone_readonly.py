"""Read-only HackerOne researcher API importer. Discovery is never authorization."""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping

from bounty_scout import AuthorizationStatus, BountyPlatform, DiscoveredTarget

BASE = "https://api.hackerone.com"
HANDLE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\Z")
MAX_RESPONSE = 2_000_000


class HackerOneReadError(RuntimeError):
    """Sanitized API error with no response body or credential disclosure."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _path(kind: str, handle: str | None = None) -> str:
    if kind == "programs" and handle is None:
        return "/v1/hackers/programs"
    if kind in {"program", "structured_scopes", "scope_exclusions"} and isinstance(handle, str) and HANDLE.fullmatch(handle):
        root = f"/v1/hackers/programs/{handle}"
        return root if kind == "program" else f"{root}/{kind}"
    raise HackerOneReadError("Endpoint not allowlisted")


class HackerOneReadOnly:
    def __init__(self, username: str | None = None, token: str | None = None):
        self._username = username if username is not None else os.getenv("HACKERONE_USERNAME", "")
        self._token = token if token is not None else os.getenv("HACKERONE_API_TOKEN", "")
        if not self._username or not self._username.strip() or not self._token or not self._token.strip():
            raise HackerOneReadError("HackerOne credentials missing")
        if any(c in self._username for c in "\r\n:") or any(c in self._token for c in "\r\n"):
            raise HackerOneReadError("Invalid credentials format")

    def get(self, kind: str, handle: str | None = None) -> dict:
        path = _path(kind, handle)
        auth = base64.b64encode(f"{self._username}:{self._token}".encode()).decode("ascii")
        req = urllib.request.Request(BASE + path, method="GET", headers={
            "Authorization": "Basic " + auth, "Accept": "application/json",
        })
        try:
            with urllib.request.build_opener(_NoRedirect).open(req, timeout=15) as response:
                if response.status != 200:
                    raise HackerOneReadError("Unexpected API status")
                data = response.read(MAX_RESPONSE + 1)
                if len(data) > MAX_RESPONSE:
                    raise HackerOneReadError("API response too large")
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                raise HackerOneReadError("API redirect rejected") from None
            if exc.code in {401, 403}:
                raise HackerOneReadError("API authentication or permission denied") from None
            if exc.code == 429:
                raise HackerOneReadError("API rate limited") from None
            raise HackerOneReadError("API HTTP request failed") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            raise HackerOneReadError("API connection failed") from None
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError):
            raise HackerOneReadError("Malformed API JSON") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), (dict, list)):
            raise HackerOneReadError("Malformed API payload")
        return payload

    def programs(self) -> list[DiscoveredTarget]:
        payload = self.get("programs")
        if not isinstance(payload["data"], list):
            raise HackerOneReadError("Malformed programs list")
        return [program_to_target(item) for item in payload["data"]]


def program_to_target(item: Mapping) -> DiscoveredTarget:
    """Import only discovery metadata; never mark scope as verified."""
    if not isinstance(item, Mapping) or item.get("type") != "program":
        raise HackerOneReadError("Malformed program object")
    attrs = item.get("attributes")
    if not isinstance(attrs, Mapping):
        raise HackerOneReadError("Malformed program attributes")
    handle = attrs.get("handle")
    if not isinstance(handle, str) or not HANDLE.fullmatch(handle):
        raise HackerOneReadError("Invalid program handle")
    name = attrs.get("name")
    return DiscoveredTarget(
        target_id=f"hackerone-{handle}",
        program_name=name if isinstance(name, str) and name.strip() else handle,
        platform=BountyPlatform.HACKERONE,
        platform_url=f"https://hackerone.com/{handle}",
        authorization_status=AuthorizationStatus.SCOPE_UNVERIFIED,
        verification_method="", verified_at="", last_verified_at="",
        in_scope_assets=[], out_of_scope_assets=[], crawler_evidence=[],
    )
