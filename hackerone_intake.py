"""Read-only HackerOne program scope intake.

Fetches the current program policy, structured scopes, and scope exclusions for a
single HackerOne program. Credentials are accepted only through environment
variables so they do not appear in process arguments or generated artifacts.
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


API_ORIGIN = "https://api.hackerone.com"
PROGRAM_HANDLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "discoveries" / "hackerone"
MAX_PAGES = 100
MAX_CRAWL_PROGRAMS = 100


class HackerOneAPIError(RuntimeError):
    """A safe-to-display HackerOne API failure."""


ResponseOpener = Callable[..., Any]


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects before a credentialed follow-up request is created."""

    def _reject(
        self,
        request: urllib.request.Request,
        response: Any,
        code: int,
        message: str,
        headers: Any,
    ) -> None:
        raise urllib.error.HTTPError(request.full_url, code, message, headers, response)

    http_error_301 = _reject
    http_error_302 = _reject
    http_error_303 = _reject
    http_error_307 = _reject
    http_error_308 = _reject


def _urlopen_without_redirects(request: urllib.request.Request, *, timeout: int) -> Any:
    opener = urllib.request.build_opener(_RejectRedirectHandler())
    return opener.open(request, timeout=timeout)


def validate_program_handle(handle: str) -> str:
    """Return a validated HackerOne program handle."""
    if not PROGRAM_HANDLE_RE.fullmatch(handle):
        raise ValueError(
            "program handle must contain only letters, numbers, hyphens, and underscores"
        )
    return handle


class HackerOneClient:
    """Minimal read-only client for the HackerOne Hacker API."""

    def __init__(
        self,
        username: str,
        token: str,
        *,
        opener: ResponseOpener | None = None,
        timeout: int = 30,
    ) -> None:
        if not username or not token:
            raise ValueError("HackerOne username and API token are required")
        if any(character in username for character in (":", "\r", "\n")):
            raise ValueError("HackerOne username contains invalid characters")
        if any(character in token for character in ("\r", "\n")):
            raise ValueError("HackerOne API token contains invalid characters")

        credential = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("ascii")
        self._authorization = f"Basic {credential}"
        self._opener = opener if opener is not None else _urlopen_without_redirects
        self._timeout = timeout

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.hackerone.com"
            or not parsed.path.startswith("/v1/hackers/")
        ):
            raise HackerOneAPIError("refused an unexpected HackerOne pagination URL")

    def _get(self, url: str) -> dict[str, Any]:
        self._validate_url(url)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": self._authorization,
                "User-Agent": "ANCHOR-HackerOne-Intake/1.0",
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                message = "HackerOne rejected the username or API token (HTTP 401)"
            elif exc.code == 403:
                message = "HackerOne denied access to this program (HTTP 403)"
            elif exc.code == 404:
                message = "HackerOne program was not found or is not accessible (HTTP 404)"
            elif exc.code == 429:
                message = "HackerOne rate limit reached (HTTP 429)"
            else:
                message = f"HackerOne API request failed (HTTP {exc.code})"
            raise HackerOneAPIError(message) from None
        except urllib.error.URLError as exc:
            raise HackerOneAPIError(f"HackerOne API connection failed: {exc.reason}") from None
        except (http.client.HTTPException, OSError):
            raise HackerOneAPIError("HackerOne API response could not be read") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HackerOneAPIError("HackerOne API returned an invalid JSON response") from None

        if not isinstance(payload, dict):
            raise HackerOneAPIError("HackerOne API returned an unexpected response shape")
        return payload

    def _get_collection(self, url: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for _ in range(MAX_PAGES):
            if url in seen_urls:
                raise HackerOneAPIError("HackerOne pagination loop detected")
            seen_urls.add(url)

            payload = self._get(url)
            data = payload.get("data")
            if not isinstance(data, list):
                raise HackerOneAPIError("HackerOne collection response is missing a data list")
            records.extend(record for record in data if isinstance(record, dict))

            links = payload.get("links") or {}
            next_url = links.get("next") if isinstance(links, dict) else None
            if not next_url:
                return records
            if not isinstance(next_url, str):
                raise HackerOneAPIError("HackerOne pagination link has an invalid type")
            self._validate_url(next_url)
            url = next_url

        raise HackerOneAPIError(f"HackerOne response exceeded the {MAX_PAGES}-page limit")

    def get_program_snapshot(self, handle: str) -> dict[str, Any]:
        """Fetch a conservative scope snapshot for one program."""
        handle = validate_program_handle(handle)
        base_url = f"{API_ORIGIN}/v1/hackers/programs/{handle}"
        program_payload = self._get(base_url)
        program = program_payload.get("data")
        if (
            not isinstance(program, dict)
            and program_payload.get("type") == "program"
            and isinstance(program_payload.get("attributes"), dict)
        ):
            program = program_payload
        if not isinstance(program, dict):
            fields = ", ".join(sorted(str(key) for key in program_payload)) or "none"
            raise HackerOneAPIError(
                "HackerOne program response is missing its data object "
                f"(top-level fields: {fields})"
            )

        return {
            "schema_version": "1.0",
            "source": "hackerone_hacker_api",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "program_handle": handle,
            "review_required": True,
            "authorization_note": (
                "This snapshot is scope evidence only. Review the policy, asset instructions, "
                "and exclusions before any active testing."
            ),
            "program": program,
            "structured_scopes": self._get_collection(f"{base_url}/structured_scopes"),
            "scope_exclusions": self._get_collection(f"{base_url}/scope_exclusions"),
        }

    def list_programs(self) -> list[dict[str, Any]]:
        """Return every program visible to the authenticated researcher."""
        return self._get_collection(f"{API_ORIGIN}/v1/hackers/programs?page[size]=100")


def _program_attributes(program: dict[str, Any]) -> dict[str, Any]:
    attributes = program.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def select_crawl_candidates(
    programs: list[dict[str, Any]],
    *,
    include_vdp: bool = False,
) -> list[dict[str, Any]]:
    """Select and rank programs that currently accept researcher submissions."""
    candidates: list[dict[str, Any]] = []
    for program in programs:
        attributes = _program_attributes(program)
        handle = attributes.get("handle")
        if not isinstance(handle, str) or not PROGRAM_HANDLE_RE.fullmatch(handle):
            continue
        if attributes.get("submission_state") != "open":
            continue
        if not include_vdp and attributes.get("offers_bounties") is not True:
            continue
        candidates.append(program)

    def rank(program: dict[str, Any]) -> tuple[int, int, int, str]:
        attributes = _program_attributes(program)
        return (
            -int(attributes.get("offers_bounties") is True),
            -int(attributes.get("gold_standard_safe_harbor") is True),
            -int(attributes.get("open_scope") is True),
            str(attributes.get("handle", "")).lower(),
        )

    return sorted(candidates, key=rank)


def crawl_programs(
    client: HackerOneClient,
    *,
    output_dir: Path,
    limit: int,
    include_vdp: bool = False,
) -> dict[str, Any]:
    """Snapshot a bounded set of open HackerOne programs and write an index."""
    if not 1 <= limit <= MAX_CRAWL_PROGRAMS:
        raise ValueError(f"crawl limit must be between 1 and {MAX_CRAWL_PROGRAMS}")

    visible_programs = client.list_programs()
    candidates = select_crawl_candidates(visible_programs, include_vdp=include_vdp)
    selected = candidates[:limit]
    results: list[dict[str, Any]] = []

    for program in selected:
        attributes = _program_attributes(program)
        handle = str(attributes["handle"])
        try:
            snapshot = client.get_program_snapshot(handle)
            output_path = write_snapshot(snapshot, output_dir)
            eligible_scopes = sum(
                1
                for scope in snapshot["structured_scopes"]
                if _program_attributes(scope).get("eligible_for_submission") is True
            )
            results.append(
                {
                    "program_handle": handle,
                    "name": attributes.get("name", handle),
                    "status": "snapshotted",
                    "offers_bounties": attributes.get("offers_bounties") is True,
                    "scope_count": len(snapshot["structured_scopes"]),
                    "eligible_scope_count": eligible_scopes,
                    "output_file": output_path.name,
                }
            )
        except HackerOneAPIError as exc:
            results.append(
                {
                    "program_handle": handle,
                    "name": attributes.get("name", handle),
                    "status": "error",
                    "error": str(exc),
                }
            )

    index = {
        "schema_version": "1.0",
        "source": "hackerone_hacker_api",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "review_required": True,
        "include_vdp": include_vdp,
        "visible_program_count": len(visible_programs),
        "candidate_program_count": len(candidates),
        "selected_program_count": len(selected),
        "programs": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "crawl-index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def write_snapshot(snapshot: dict[str, Any], output_dir: Path) -> Path:
    """Write a snapshot without placing credentials in the output."""
    handle = validate_program_handle(str(snapshot.get("program_handle", "")))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{handle}-scope.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--program-handle")
    mode.add_argument("--crawl", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument(
        "--include-vdp",
        action="store_true",
        help="include open vulnerability disclosure programs that do not offer bounties",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    username = os.environ.get("HACKERONE_USERNAME", "")
    token = os.environ.get("HACKERONE_API_TOKEN", "")

    try:
        client = HackerOneClient(username, token)
        if args.crawl:
            index = crawl_programs(
                client,
                output_dir=args.output_dir,
                limit=args.limit,
                include_vdp=args.include_vdp,
            )
            print(
                "Wrote HackerOne crawl with "
                f"{index['selected_program_count']} selected programs to {args.output_dir}"
            )
        else:
            snapshot = client.get_program_snapshot(args.program_handle)
            output_path = write_snapshot(snapshot, args.output_dir)
            print(f"Wrote read-only HackerOne scope snapshot to {output_path}")
    except (ValueError, HackerOneAPIError) as exc:
        print(f"HackerOne intake failed: {exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
