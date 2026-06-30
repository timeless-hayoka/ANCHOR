"""Target code identity verification for protected analysis."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from bugbot.scope import (
    IDENTITY_LOCAL_FIXTURE_UNPINNED,
    IDENTITY_VERIFIED_REPO,
    ScopeGrant,
)

_IDENTITY_BLOCKED_REASON = "target identity could not be verified"
_ALLOWED_ACTIONS_ON_BLOCK = "scope review and planning only"


@dataclass(frozen=True)
class TargetIdentityResult:
    verified: bool
    identity_status: str
    summary: str
    blocked_reason: str | None = None


def normalize_git_remote(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    ssh_match = re.match(r"^git@([^:]+):(.+)$", cleaned)
    if ssh_match:
        host, path = ssh_match.groups()
        cleaned = f"https://{host}/{path}"
    parsed = urlparse(cleaned.lower())
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc}{path}"


def _run_git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _git_head(workspace: Path) -> str | None:
    result = _run_git(workspace, "rev-parse", "HEAD")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_origin_url(workspace: Path) -> str | None:
    result = _run_git(workspace, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _head_matches_ref(head: str, expected_ref: str) -> bool:
    return head.strip().lower() == expected_ref.strip().lower()


def verify_target_identity(workspace: Path, grant: ScopeGrant) -> TargetIdentityResult:
    """Verify workspace identity according to the scope grant policy."""
    identity_status = grant.identity_status

    if identity_status == IDENTITY_LOCAL_FIXTURE_UNPINNED:
        if (workspace / ".git").is_dir():
            head = _git_head(workspace)
            summary = (
                f"identity_status={IDENTITY_LOCAL_FIXTURE_UNPINNED}; "
                f"git_head={head[:12] if head else 'unknown'}"
            )
        else:
            summary = (
                f"identity_status={IDENTITY_LOCAL_FIXTURE_UNPINNED}; "
                "target_ref unpinned (non-git workspace)"
            )
        return TargetIdentityResult(
            verified=True,
            identity_status=IDENTITY_LOCAL_FIXTURE_UNPINNED,
            summary=summary,
        )

    if identity_status != IDENTITY_VERIFIED_REPO:
        return TargetIdentityResult(
            verified=False,
            identity_status=identity_status,
            summary="unsupported identity_status",
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    if not grant.target_repo_url:
        return TargetIdentityResult(
            verified=False,
            identity_status=IDENTITY_VERIFIED_REPO,
            summary="missing approved target_repo_url in scope grant",
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    if not (workspace / ".git").is_dir():
        return TargetIdentityResult(
            verified=False,
            identity_status=IDENTITY_VERIFIED_REPO,
            summary="workspace is not a git repository",
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    head = _git_head(workspace)
    if head is None:
        return TargetIdentityResult(
            verified=False,
            identity_status=IDENTITY_VERIFIED_REPO,
            summary="unable to read git HEAD",
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    if not _head_matches_ref(head, grant.target_ref):
        return TargetIdentityResult(
            verified=False,
            identity_status=IDENTITY_VERIFIED_REPO,
            summary=f"HEAD {head} does not exactly match target_ref {grant.target_ref}",
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    origin = _git_origin_url(workspace)
    if origin is None:
        return TargetIdentityResult(
            verified=False,
            identity_status=IDENTITY_VERIFIED_REPO,
            summary="remote origin is not configured",
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    if normalize_git_remote(origin) != normalize_git_remote(grant.target_repo_url):
        return TargetIdentityResult(
            verified=False,
            identity_status=IDENTITY_VERIFIED_REPO,
            summary=(
                f"origin {origin} does not match approved repo {grant.target_repo_url}"
            ),
            blocked_reason=_IDENTITY_BLOCKED_REASON,
        )

    branch_check = _run_git(workspace, "symbolic-ref", "-q", "HEAD")
    if branch_check.returncode == 0:
        branch_head = _git_head(workspace)
        if branch_head is None or not _head_matches_ref(branch_head, grant.target_ref):
            return TargetIdentityResult(
                verified=False,
                identity_status=IDENTITY_VERIFIED_REPO,
                summary="branch HEAD is not pinned to target_ref",
                blocked_reason=_IDENTITY_BLOCKED_REASON,
            )

    return TargetIdentityResult(
        verified=True,
        identity_status=IDENTITY_VERIFIED_REPO,
        summary=f"verified repo at {head[:12]} with matching origin",
    )


def blocked_identity_message(result: TargetIdentityResult) -> str:
    return (
        "Analysis: BLOCKED\n"
        f"Reason: {result.blocked_reason or _IDENTITY_BLOCKED_REASON}\n"
        f"Allowed actions: {_ALLOWED_ACTIONS_ON_BLOCK}\n"
        f"Detail: {result.summary}"
    )
