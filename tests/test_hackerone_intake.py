"""Tests for the read-only HackerOne scope intake."""

from __future__ import annotations

import io
import json
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from hackerone_intake import (
    HackerOneAPIError,
    HackerOneClient,
    _RejectRedirectHandler,
    crawl_programs,
    select_crawl_candidates,
    validate_program_handle,
    write_snapshot,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def response(payload: dict) -> FakeResponse:
    return FakeResponse(json.dumps(payload).encode("utf-8"))


def test_fetches_program_scopes_and_exclusions_with_pagination() -> None:
    requests: list[Request] = []

    def opener(request: Request, *, timeout: int) -> FakeResponse:
        requests.append(request)
        assert timeout == 30
        url = request.full_url
        if url.endswith("/programs/acme"):
            return response({"data": {"id": "7", "attributes": {"policy": "Rules"}}})
        if url.endswith("/structured_scopes"):
            return response(
                {
                    "data": [{"id": "1", "attributes": {"asset_identifier": "a.example"}}],
                    "links": {
                        "next": "https://api.hackerone.com/v1/hackers/programs/acme/structured_scopes?page[number]=2"
                    },
                }
            )
        if "structured_scopes?page" in url:
            return response({"data": [{"id": "2"}], "links": {}})
        if url.endswith("/scope_exclusions"):
            return response({"data": [{"id": "9", "attributes": {"category": "spam"}}]})
        raise AssertionError(f"unexpected URL: {url}")

    snapshot = HackerOneClient("researcher", "secret-token", opener=opener).get_program_snapshot(
        "acme"
    )

    assert snapshot["program_handle"] == "acme"
    assert snapshot["review_required"] is True
    assert [item["id"] for item in snapshot["structured_scopes"]] == ["1", "2"]
    assert [item["id"] for item in snapshot["scope_exclusions"]] == ["9"]
    assert len(requests) == 4
    assert all(request.get_header("Authorization", "").startswith("Basic ") for request in requests)
    assert "secret-token" not in json.dumps(snapshot)


def test_accepts_live_unwrapped_program_resource_shape() -> None:
    def opener(request: Request, *, timeout: int) -> FakeResponse:
        url = request.full_url
        if url.endswith("/programs/acme"):
            return response(
                {
                    "id": "7",
                    "type": "program",
                    "attributes": {"handle": "acme", "policy": "Rules"},
                    "relationships": {"structured_scopes": {"data": []}},
                }
            )
        if url.endswith("/structured_scopes") or url.endswith("/scope_exclusions"):
            return response({"data": []})
        raise AssertionError(f"unexpected URL: {url}")

    snapshot = HackerOneClient("researcher", "token", opener=opener).get_program_snapshot(
        "acme"
    )

    assert snapshot["program"]["type"] == "program"
    assert snapshot["program"]["attributes"]["handle"] == "acme"
    assert snapshot["structured_scopes"] == []
    assert snapshot["scope_exclusions"] == []


@pytest.mark.parametrize("handle", ["../other", "acme/other", "acme?x=1", "acme name", ""])
def test_rejects_unsafe_program_handles(handle: str) -> None:
    with pytest.raises(ValueError):
        validate_program_handle(handle)


def test_rejects_off_origin_pagination_url() -> None:
    def opener(_request: Request, *, timeout: int) -> FakeResponse:
        return response(
            {
                "data": [],
                "links": {"next": "https://attacker.example/collect"},
            }
        )

    client = HackerOneClient("researcher", "token", opener=opener)
    with pytest.raises(HackerOneAPIError, match="unexpected HackerOne pagination URL"):
        client._get_collection(
            "https://api.hackerone.com/v1/hackers/programs/acme/structured_scopes"
        )


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_default_redirect_handler_rejects_redirects(status: int) -> None:
    request = Request(
        "https://api.hackerone.com/v1/hackers/programs/acme",
        headers={"Authorization": "Basic credential"},
    )
    handler = _RejectRedirectHandler()

    with pytest.raises(HTTPError) as exc_info:
        getattr(handler, f"http_error_{status}")(
            request,
            FakeResponse(),
            status,
            "Redirect",
            {"Location": "http://attacker.example/collect"},
        )

    assert exc_info.value.code == status


def test_http_errors_do_not_disclose_credentials() -> None:
    def opener(request: Request, *, timeout: int) -> FakeResponse:
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    client = HackerOneClient("researcher", "top-secret", opener=opener)
    with pytest.raises(HackerOneAPIError) as exc_info:
        client.get_program_snapshot("acme")

    assert "top-secret" not in str(exc_info.value)
    assert "researcher" not in str(exc_info.value)


def test_missing_program_data_reports_only_top_level_field_names() -> None:
    def opener(_request: Request, *, timeout: int) -> FakeResponse:
        return response(
            {
                "meta": {"request_id": "sensitive-request-id"},
                "errors": [{"detail": "sensitive API response detail"}],
            }
        )

    client = HackerOneClient("researcher", "top-secret", opener=opener)
    with pytest.raises(HackerOneAPIError) as exc_info:
        client.get_program_snapshot("acme")

    message = str(exc_info.value)
    assert "top-level fields: errors, meta" in message
    assert "sensitive-request-id" not in message
    assert "sensitive API response detail" not in message
    assert "top-secret" not in message


def test_incomplete_response_is_converted_to_safe_api_error() -> None:
    class IncompleteResponse(FakeResponse):
        def read(self, *_args, **_kwargs):
            raise IncompleteRead(b'{"partial": "secret-fragment"')

    def opener(_request: Request, *, timeout: int) -> FakeResponse:
        return IncompleteResponse()

    client = HackerOneClient("researcher", "top-secret", opener=opener)

    with pytest.raises(HackerOneAPIError, match="response could not be read") as exc_info:
        client._get("https://api.hackerone.com/v1/hackers/programs/acme")

    assert "secret-fragment" not in str(exc_info.value)
    assert "top-secret" not in str(exc_info.value)


def test_writes_snapshot_to_handle_specific_file(tmp_path: Path) -> None:
    snapshot = {"program_handle": "acme", "structured_scopes": []}
    output = write_snapshot(snapshot, tmp_path)

    assert output == tmp_path / "acme-scope.json"
    assert json.loads(output.read_text(encoding="utf-8")) == snapshot


def program(
    handle: str,
    *,
    submission_state: str = "open",
    offers_bounties: bool = True,
    safe_harbor: bool = False,
    open_scope: bool = False,
) -> dict:
    return {
        "id": handle,
        "type": "program",
        "attributes": {
            "handle": handle,
            "name": handle.title(),
            "submission_state": submission_state,
            "offers_bounties": offers_bounties,
            "gold_standard_safe_harbor": safe_harbor,
            "open_scope": open_scope,
        },
    }


def test_selects_open_bounty_programs_and_ranks_safer_options_first() -> None:
    programs = [
        program("closed", submission_state="paused", safe_harbor=True),
        program("vdp", offers_bounties=False),
        program("ordinary"),
        program("wide", open_scope=True),
        program("safe", safe_harbor=True),
    ]

    selected = select_crawl_candidates(programs)

    assert [item["attributes"]["handle"] for item in selected] == [
        "safe",
        "wide",
        "ordinary",
    ]


def test_can_include_open_vulnerability_disclosure_programs() -> None:
    selected = select_crawl_candidates(
        [program("bounty"), program("vdp", offers_bounties=False)],
        include_vdp=True,
    )
    assert [item["attributes"]["handle"] for item in selected] == ["bounty", "vdp"]


def test_crawl_is_bounded_writes_snapshots_and_records_errors(tmp_path: Path) -> None:
    class FakeClient:
        def list_programs(self) -> list[dict]:
            return [program("alpha", safe_harbor=True), program("bravo"), program("charlie")]

        def get_program_snapshot(self, handle: str) -> dict:
            if handle == "bravo":
                raise HackerOneAPIError("program unavailable")
            return {
                "program_handle": handle,
                "structured_scopes": [
                    {
                        "id": "1",
                        "attributes": {"eligible_for_submission": handle == "alpha"},
                    }
                ],
                "scope_exclusions": [],
            }

    index = crawl_programs(FakeClient(), output_dir=tmp_path, limit=2)

    assert index["visible_program_count"] == 3
    assert index["candidate_program_count"] == 3
    assert index["selected_program_count"] == 2
    assert [item["status"] for item in index["programs"]] == ["snapshotted", "error"]
    assert index["programs"][0]["eligible_scope_count"] == 1
    assert (tmp_path / "alpha-scope.json").is_file()
    assert (tmp_path / "crawl-index.json").is_file()
    assert not (tmp_path / "charlie-scope.json").exists()


@pytest.mark.parametrize("limit", [0, 101])
def test_rejects_unsafe_crawl_limits(tmp_path: Path, limit: int) -> None:
    class FakeClient:
        def list_programs(self) -> list[dict]:
            raise AssertionError("network should not be used")

    with pytest.raises(ValueError, match="crawl limit"):
        crawl_programs(FakeClient(), output_dir=tmp_path, limit=limit)
