from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = ROOT / "discoveries" / "github"
DEFAULT_SEARCH_QUERIES = [
    "smart contract security fuzzing invariant testing",
    "solidity foundry echidna slither",
    "smart contract documentation testing",
]

STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "into",
    "this",
    "that",
    "you",
    "your",
    "our",
    "repo",
    "repos",
    "github",
    "issue",
    "issues",
    "test",
    "tests",
    "docs",
    "documentation",
}


class GitHubDiscoveryError(RuntimeError):
    pass


class GitHubRateLimitError(GitHubDiscoveryError):
    def __init__(self, message: str, *, reset_at: str | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.reset_at = reset_at
        self.retry_after = retry_after


class GitHubAPIError(GitHubDiscoveryError):
    pass


@dataclass
class RepoSignal:
    name: str
    value: str
    weight: int


@dataclass
class RepoCandidate:
    full_name: str
    html_url: str
    description: str
    stars: int
    forks: int
    open_issues: int
    pushed_at: str
    updated_at: str
    archived: bool
    fork: bool
    language: str
    topics: list[str] = field(default_factory=list)
    docs_present: bool = False
    readme_excerpt: str = ""
    priority_score: int = 0
    authorization_state: str = "Public repo / no confirmed bounty scope"
    review_state: str = "Needs scope confirmation"
    suggested_posture: str = "Passive review only until scope is confirmed"
    likely_surface: list[str] = field(default_factory=list)
    security_signals: list[str] = field(default_factory=list)
    dependency_manifests: list[str] = field(default_factory=list)
    workflow_tools: list[str] = field(default_factory=list)
    release_cadence: str = "unknown"
    evidence_sources: list[dict[str, Any]] = field(default_factory=list)
    score: int = 0
    recommendation: str = "watch"
    reasons: list[str] = field(default_factory=list)
    signals: list[RepoSignal] = field(default_factory=list)
    query_matches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "html_url": self.html_url,
            "description": self.description,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
            "pushed_at": self.pushed_at,
            "updated_at": self.updated_at,
            "archived": self.archived,
            "fork": self.fork,
            "language": self.language,
            "topics": list(self.topics),
            "docs_present": self.docs_present,
            "readme_excerpt": self.readme_excerpt,
            "priority_score": self.priority_score,
            "authorization_state": self.authorization_state,
            "review_state": self.review_state,
            "suggested_posture": self.suggested_posture,
            "likely_surface": list(self.likely_surface),
            "security_signals": list(self.security_signals),
            "dependency_manifests": list(self.dependency_manifests),
            "workflow_tools": list(self.workflow_tools),
            "release_cadence": self.release_cadence,
            "evidence_sources": list(self.evidence_sources),
            "score": self.score,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "signals": [signal.__dict__ for signal in self.signals],
            "query_matches": list(self.query_matches),
        }


def utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "entry").lower()).strip("-")
    return slug or "entry"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def parse_iso8601(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def tokenize_query(query: str) -> list[str]:
    tokens: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9_.-]+", query.lower()):
        if len(raw) < 3:
            continue
        if raw in STOPWORDS:
            continue
        if ":" in raw:
            continue
        tokens.append(raw)
    return tokens


def get_github_token() -> str | None:
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_API_TOKEN"):
        value = os.getenv(env_name)
        if value:
            return value.strip()
    try:
        result = subprocess.run(["gh", "auth", "token"], check=True, capture_output=True, text=True)
        token = result.stdout.strip()
        return token or None
    except Exception:
        return None


def github_api_get_json(path: str, params: dict[str, Any] | None = None, token: str | None = None) -> dict[str, Any]:
    url = f"https://api.github.com{path}"
    if params:
        query = urllib.parse.urlencode([(key, value) for key, value in params.items() if value is not None], doseq=True)
        if query:
            url = f"{url}?{query}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ANCHOR-GitHub-Discovery",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        if exc.code in {403, 429} and "rate" in details.lower():
            reset_header = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
            retry_after_header = exc.headers.get("Retry-After") if exc.headers else None
            raise GitHubRateLimitError(
                f"GitHub rate limit hit for {path}: {exc.code} {details}",
                reset_at=str(reset_header) if reset_header else None,
                retry_after=int(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None,
            ) from exc
        raise GitHubAPIError(f"GitHub API request failed for {path}: {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise GitHubAPIError(f"GitHub API request failed for {path}: {exc}") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise GitHubAPIError(f"Malformed JSON payload from {path}") from exc
    if not isinstance(data, dict):
        raise GitHubAPIError(f"Unexpected JSON payload shape from {path}")
    return data


def github_api_get_text(path: str, token: str | None = None) -> str:
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ANCHOR-GitHub-Discovery",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ""
        details = exc.read().decode("utf-8", errors="replace")
        if exc.code in {403, 429} and "rate" in details.lower():
            reset_header = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
            retry_after_header = exc.headers.get("Retry-After") if exc.headers else None
            raise GitHubRateLimitError(
                f"GitHub rate limit hit for {path}: {exc.code} {details}",
                reset_at=str(reset_header) if reset_header else None,
                retry_after=int(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None,
            ) from exc
        raise GitHubAPIError(f"GitHub API request failed for {path}: {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise GitHubAPIError(f"GitHub API request failed for {path}: {exc}") from exc


def github_api_get_listing(path: str, token: str | None = None) -> list[dict[str, Any]]:
    payload = github_api_get_json(path, token=token)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def list_repo_contents(full_name: str, path: str = "", token: str | None = None) -> list[dict[str, Any]]:
    suffix = f"/{path}" if path else ""
    try:
        return github_api_get_listing(f"/repos/{full_name}/contents{suffix}", token=token)
    except Exception:
        return []


def read_repo_file(full_name: str, path: str, token: str | None = None) -> str:
    try:
        return github_api_get_text(f"/repos/{full_name}/contents/{path}", token=token)
    except Exception:
        return ""


def scan_workflow_tools(workflow_text: str) -> list[str]:
    tools = []
    lower = workflow_text.lower()
    for name, needle in [
        ("CodeQL", "codeql"),
        ("Semgrep", "semgrep"),
        ("Slither", "slither"),
        ("Foundry", "foundry"),
        ("Forge", "forge "),
        ("Echidna", "echidna"),
        ("Mythril", "mythril"),
        ("pytest", "pytest"),
        ("cargo test", "cargo test"),
        ("go test", "go test"),
        ("npm test", "npm test"),
    ]:
        if needle in lower and name not in tools:
            tools.append(name)
    return tools


def scan_public_signals(full_name: str, readme: str, token: str | None = None, source_log: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root_entries = list_repo_contents(full_name, token=token)
    github_entries = list_repo_contents(full_name, ".github", token=token)
    workflow_entries = list_repo_contents(full_name, ".github/workflows", token=token)

    if source_log is not None:
        source_log.extend([
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}", "note": "repository metadata"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/readme", "note": "README"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/contents", "note": "root listing"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/contents/.github", "note": ".github listing"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/contents/.github/workflows", "note": "workflow listing"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/releases?per_page=5", "note": "releases"},
        ])

    root_names = {str(entry.get("name", "")) for entry in root_entries if entry.get("name")}
    github_names = {str(entry.get("name", "")) for entry in github_entries if entry.get("name")}
    workflow_names = [str(entry.get("name", "")) for entry in workflow_entries if entry.get("name")]

    security_paths = []
    for candidate in (".github/SECURITY.md", "SECURITY.md", ".github/security.md", "security.md"):
        if candidate.split("/")[-1] in root_names or candidate.split("/")[-1] in github_names:
            security_paths.append(candidate)

    dependency_manifests = [
        name
        for name in [
            "foundry.toml",
            "package.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "package-lock.json",
            "pyproject.toml",
            "requirements.txt",
            "Pipfile",
            "Cargo.toml",
            "go.mod",
            "Makefile",
            "Dockerfile",
        ]
        if name in root_names
    ]

    workflow_tools: list[str] = []
    workflow_signals: list[str] = []
    for entry in workflow_entries:
        path = str(entry.get("path") or "")
        if not path:
            continue
        workflow_signals.append(path)
        workflow_text = read_repo_file(full_name, path, token=token)
        workflow_tools.extend(scan_workflow_tools(workflow_text))

    workflow_tools = sorted(set(workflow_tools))
    audit_mentions = any(term in (readme or "").lower() for term in ("audit", "advisory", "bug bounty", "security policy", "scope", "immunefi", "hackerone"))
    tests_present = any(name in root_names for name in ("test", "tests", "spec", "__tests__"))
    fuzz_present = any(term in (readme or "").lower() for term in ("fuzz", "echidna", "foundry", "invariant"))
    codeql_present = any("codeql" in tool.lower() for tool in workflow_tools)
    semgrep_present = any("semgrep" in tool.lower() for tool in workflow_tools)
    slither_present = any("slither" in tool.lower() for tool in workflow_tools)
    foundry_present = any(term in (readme or "").lower() for term in ("foundry", "forge"))
    release_list = []
    try:
        release_list = github_api_get_json(f"/repos/{full_name}/releases?per_page=5", token=token)
    except Exception:
        release_list = []
    last_release = ""
    if isinstance(release_list, list) and release_list:
        first_release = release_list[0] if isinstance(release_list[0], dict) else {}
        last_release = str(first_release.get("published_at") or first_release.get("created_at") or "")
    release_cadence = "inactive"
    release_dt = parse_iso8601(last_release)
    if release_dt is not None:
        age_days = (dt.datetime.now(dt.timezone.utc) - release_dt).days
        if age_days <= 90:
            release_cadence = "active"
        elif age_days <= 365:
            release_cadence = "moderate"
        else:
            release_cadence = "slow"

    likely_surface: list[str] = []
    lower_blob = (readme or "").lower()
    if any(term in lower_blob for term in ("solidity", "smart contract", "contract", "openzeppelin")):
        likely_surface.append("smart-contract logic")
    if any(term in lower_blob for term in ("upgrade", "proxy", "initializer", "uups")):
        likely_surface.append("upgradeability")
    if any(term in lower_blob for term in ("access control", "permission", "role", "owner")):
        likely_surface.append("access control")
    if any(term in lower_blob for term in ("call", "delegatecall", "external call", "reentrancy")):
        likely_surface.append("external calls")
    if any(term in lower_blob for term in ("parse", "json", "yaml", "serialize", "deserialize", "protobuf")):
        likely_surface.append("parsing / serialization")
    if dependency_manifests:
        likely_surface.append("dependency risk")
    if tests_present or fuzz_present or workflow_tools:
        likely_surface.append("tests / fuzzing / CI")
    likely_surface = list(dict.fromkeys(likely_surface))[:5]

    security_signals = []
    security_signals.append("SECURITY.md present" if security_paths else "SECURITY.md absent")
    security_signals.append("CodeQL present" if codeql_present else "CodeQL absent")
    security_signals.append("Semgrep present" if semgrep_present else "Semgrep absent")
    security_signals.append("Slither present" if slither_present else "Slither absent")
    security_signals.append("tests/fuzzing present" if (tests_present or fuzz_present) else "tests/fuzzing not obvious")
    security_signals.append("dependency manifests present" if dependency_manifests else "dependency manifests absent")
    security_signals.append("audit/advisory language present" if audit_mentions else "no audit/advisory language found")
    security_signals.append(f"release cadence: {release_cadence}")

    if audit_mentions:
        authorization_state = "Explicitly authorized bounty / audit scope"
        review_state = "Explicitly authorized bounty / audit scope"
        suggested_posture = "Local clone analysis allowed and scope-limited review is encouraged"
    elif security_paths or codeql_present or tests_present or workflow_tools:
        authorization_state = "Public repo / no confirmed bounty scope"
        review_state = "Needs scope confirmation"
        suggested_posture = "Passive review only until scope is confirmed"
    elif dependency_manifests or readme.strip():
        authorization_state = "Public repo / no confirmed bounty scope"
        review_state = "Local clone analysis allowed"
        suggested_posture = "Local clone analysis allowed"
    else:
        authorization_state = "Public repo / no confirmed bounty scope"
        review_state = "Passive-only"
        suggested_posture = "Passive review only until scope is confirmed"

    return {
        "security_paths": security_paths,
        "workflow_names": workflow_names,
        "workflow_tools": workflow_tools,
        "workflow_signals": workflow_signals,
        "dependency_manifests": dependency_manifests,
        "likely_surface": likely_surface,
        "security_signals": security_signals,
        "release_cadence": release_cadence,
        "authorization_state": authorization_state,
        "review_state": review_state,
        "suggested_posture": suggested_posture,
        "audit_mentions": audit_mentions,
        "evidence_sources": [
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}", "note": "repository metadata"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/readme", "note": "README"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/contents", "note": "root listing"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/contents/.github", "note": ".github listing"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/contents/.github/workflows", "note": "workflow listing"},
            {"type": "api", "url": f"https://api.github.com/repos/{full_name}/releases?per_page=5", "note": "releases"},
            {"type": "file", "path": "README.md", "note": "README text"},
        ],
    }


def search_repositories(query: str, *, limit: int, token: str | None = None, include_forks: bool = False, include_archived: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    page = 1
    per_page = min(100, max(1, limit))
    search_query = query.strip()
    if not include_forks and "fork:" not in search_query:
        search_query = f"{search_query} fork:false".strip()
    if not include_archived and "archived:" not in search_query:
        search_query = f"{search_query} archived:false".strip()

    while len(results) < limit:
        payload = github_api_get_json(
            "/search/repositories",
            params={
                "q": search_query,
                "sort": "updated",
                "order": "desc",
                "per_page": min(per_page, limit - len(results)),
                "page": page,
            },
            token=token,
        )
        items = payload.get("items", []) or []
        results.extend(item for item in items if isinstance(item, dict))
        if len(items) < min(per_page, limit - len(results) + len(items)):
            break
        page += 1
        if page > 10:
            break
    return results[:limit]


def fetch_repo_details(full_name: str, token: str | None = None) -> dict[str, Any]:
    return github_api_get_json(f"/repos/{full_name}", token=token)


def fetch_repo_readme(full_name: str, token: str | None = None) -> str:
    return github_api_get_text(f"/repos/{full_name}/readme", token=token)


def repo_text_blob(repo: dict[str, Any], readme: str) -> str:
    parts = [
        str(repo.get("full_name", "")),
        str(repo.get("name", "")),
        str(repo.get("description", "")),
        str(repo.get("language", "")),
        " ".join(repo.get("topics", []) or []),
        readme,
    ]
    return " ".join(parts).lower()


def compute_repo_score(repo: dict[str, Any], readme: str, query_tokens: list[str], public_signals: dict[str, Any] | None = None) -> RepoCandidate:
    full_name = str(repo.get("full_name") or f"{repo.get('owner', {}).get('login', '')}/{repo.get('name', '')}")
    signals = public_signals or {}
    candidate = RepoCandidate(
        full_name=full_name,
        html_url=str(repo.get("html_url", "")),
        description=str(repo.get("description") or "").strip(),
        stars=int(repo.get("stargazers_count") or 0),
        forks=int(repo.get("forks_count") or 0),
        open_issues=int(repo.get("open_issues_count") or 0),
        pushed_at=str(repo.get("pushed_at") or ""),
        updated_at=str(repo.get("updated_at") or ""),
        archived=bool(repo.get("archived")),
        fork=bool(repo.get("fork")),
        language=str(repo.get("language") or ""),
        topics=[str(topic) for topic in (repo.get("topics") or []) if topic],
        docs_present=bool(readme.strip()),
        readme_excerpt=readme.strip().splitlines()[0][:240] if readme.strip() else "",
        likely_surface=list(signals.get("likely_surface", []) or []),
        security_signals=list(signals.get("security_signals", []) or []),
        dependency_manifests=list(signals.get("dependency_manifests", []) or []),
        workflow_tools=list(signals.get("workflow_tools", []) or []),
        release_cadence=str(signals.get("release_cadence", "unknown") or "unknown"),
        evidence_sources=list(signals.get("evidence_sources", []) or []),
        authorization_state=str(signals.get("authorization_state", "Public repo / no confirmed bounty scope") or "Public repo / no confirmed bounty scope"),
        review_state=str(signals.get("review_state", "Needs scope confirmation") or "Needs scope confirmation"),
        suggested_posture=str(signals.get("suggested_posture", "Passive review only until scope is confirmed") or "Passive review only until scope is confirmed"),
    )

    text = repo_text_blob(repo, readme)
    score = 0

    if not candidate.archived:
        score += 2
        candidate.signals.append(RepoSignal("active", "not archived", 2))
        candidate.reasons.append("repo is not archived")
    else:
        score -= 3
        candidate.signals.append(RepoSignal("archived", "archived repo", -3))
        candidate.reasons.append("repo is archived")

    if candidate.open_issues > 0:
        score += 2
        candidate.signals.append(RepoSignal("issues", f"{candidate.open_issues} open issues", 2))
        candidate.reasons.append("open issues are present")
    else:
        score -= 1
        candidate.signals.append(RepoSignal("issues", "no open issues", -1))
        candidate.reasons.append("no open issues visible")

    if candidate.docs_present:
        score += 2
        candidate.signals.append(RepoSignal("docs", "README present", 2))
        candidate.reasons.append("README present")
        if len(readme) > 1000 or any(marker in text for marker in ("docs/", "contributing", "usage", "getting started", "invariant", "fuzz")):
            score += 1
            candidate.signals.append(RepoSignal("docs-depth", "README looks substantive", 1))
            candidate.reasons.append("README looks substantive")
    else:
        score -= 1
        candidate.signals.append(RepoSignal("docs", "README missing or empty", -1))
        candidate.reasons.append("README missing or empty")

    updated = parse_iso8601(candidate.pushed_at) or parse_iso8601(candidate.updated_at)
    if updated is not None:
        age_days = (dt.datetime.now(dt.timezone.utc) - updated).days
        if age_days <= 90:
            score += 3
            candidate.signals.append(RepoSignal("fresh", f"updated {age_days} days ago", 3))
            candidate.reasons.append("recently updated")
        elif age_days <= 365:
            score += 2
            candidate.signals.append(RepoSignal("fresh", f"updated {age_days} days ago", 2))
            candidate.reasons.append("updated within the last year")
        else:
            score += 0
            candidate.signals.append(RepoSignal("fresh", f"updated {age_days} days ago", 0))
    else:
        candidate.signals.append(RepoSignal("fresh", "timestamp unavailable", 0))

    if candidate.stars >= 1000:
        score += 2
        candidate.signals.append(RepoSignal("maturity", f"{candidate.stars} stars", 2))
    elif candidate.stars >= 100:
        score += 1
        candidate.signals.append(RepoSignal("maturity", f"{candidate.stars} stars", 1))
    elif candidate.stars == 0:
        score -= 1
        candidate.signals.append(RepoSignal("maturity", "no stars", -1))

    if candidate.fork:
        score -= 1
        candidate.signals.append(RepoSignal("fork", "forked repo", -1))

    if candidate.security_signals:
        score += sum(1 for signal in candidate.security_signals if "present" in signal.lower())
    if candidate.workflow_tools:
        score += 1
    if candidate.dependency_manifests:
        score += 1
    if candidate.release_cadence == "active":
        score += 2
    elif candidate.release_cadence == "moderate":
        score += 1

    keyword_hits = 0
    for token in query_tokens:
        if token and token in text:
            keyword_hits += 1
            candidate.query_matches.append(token)
    if keyword_hits:
        score += min(keyword_hits, 4)
        candidate.signals.append(RepoSignal("relevance", f"{keyword_hits} keyword hits", min(keyword_hits, 4)))
        candidate.reasons.append(f"{keyword_hits} query terms matched")

    topic_hits = sum(1 for topic in candidate.topics if topic.lower() in {"solidity", "foundry", "echidna", "security", "fuzzing", "invariants", "testing", "docs", "documentation"})
    if topic_hits:
        score += min(topic_hits, 3)
        candidate.signals.append(RepoSignal("topics", f"{topic_hits} matched topics", min(topic_hits, 3)))
        candidate.reasons.append(f"{topic_hits} relevant topic(s)")

    if candidate.language and candidate.language.lower() in {"solidity", "rust", "python", "typescript", "javascript"}:
        score += 1
        candidate.signals.append(RepoSignal("language", candidate.language, 1))

    candidate.score = score
    candidate.priority_score = max(0, min(100, 50 + (score * 4)))
    if score >= 9 and candidate.docs_present and candidate.open_issues > 0 and not candidate.archived:
        candidate.recommendation = "join"
    elif score >= 6:
        candidate.recommendation = "watch"
    else:
        candidate.recommendation = "skip"

    if candidate.priority_score >= 80 and candidate.review_state == "Needs scope confirmation":
        candidate.review_state = "Local clone analysis allowed"
        candidate.suggested_posture = "Local clone analysis allowed"
    if candidate.priority_score < 40 and candidate.review_state == "Needs scope confirmation":
        candidate.suggested_posture = "Passive review only until scope is confirmed"

    return candidate


def issue_angles_for_repo(candidate: RepoCandidate) -> list[str]:
    text = f"{candidate.full_name} {candidate.description} {' '.join(candidate.topics)} {candidate.readme_excerpt}".lower()
    angles: list[str] = []
    if any(term in text for term in ("solidity", "foundry", "echidna", "fuzz", "invariant", "smart contract")):
        angles.extend([
            "testing/invariants",
            "docs/workflow clarity",
            "regression harness or machine-readable output",
        ])
    elif any(term in text for term in ("docs", "documentation", "readme", "guide")):
        angles.extend([
            "docs navigation or onboarding",
            "example coverage",
            "issue templates or contribution workflow",
        ])
    else:
        angles.extend([
            "workflow clarity",
            "tests or regression coverage",
            "README / docs cleanup",
        ])
    return angles[:3]


def discover_repositories(
    queries: Iterable[str] | None = None,
    *,
    limit: int = 12,
    per_query: int = 25,
    include_forks: bool = False,
    include_archived: bool = False,
    token: str | None = None,
    fetch_readmes: bool = True,
) -> dict[str, Any]:
    token = token or get_github_token()
    active_queries = [query.strip() for query in (queries or DEFAULT_SEARCH_QUERIES) if query and query.strip()]
    if not active_queries:
        active_queries = list(DEFAULT_SEARCH_QUERIES)

    search_hits: dict[str, dict[str, Any]] = {}
    search_order: list[str] = []
    query_terms = sorted({term for query in active_queries for term in tokenize_query(query)})

    for query in active_queries:
        for item in search_repositories(query, limit=per_query, token=token, include_forks=include_forks, include_archived=include_archived):
            full_name = str(item.get("full_name") or "")
            if not full_name:
                continue
            if full_name not in search_hits:
                search_order.append(full_name)
                search_hits[full_name] = item
            else:
                existing = search_hits[full_name]
                existing["stargazers_count"] = max(int(existing.get("stargazers_count") or 0), int(item.get("stargazers_count") or 0))

    candidates: list[RepoCandidate] = []
    for full_name in search_order:
        item = search_hits[full_name]
        details = dict(item)
        readme = ""
        public_signals: dict[str, Any] = {}
        if fetch_readmes:
            try:
                details = fetch_repo_details(full_name, token=token)
                readme = fetch_repo_readme(full_name, token=token)
                public_signals = scan_public_signals(full_name, readme, token=token)
            except Exception:
                details = dict(item)
                readme = ""
        candidate = compute_repo_score(details, readme, query_terms, public_signals=public_signals)
        candidates.append(candidate)

    candidates.sort(key=lambda candidate: (candidate.score, candidate.stars, candidate.open_issues), reverse=True)
    selected = candidates[:limit]
    bundle = {
        "generated_at": utcnow_iso(),
        "queries": active_queries,
        "query_terms": query_terms,
        "source_queries": [
            {
                "type": "search",
                "url": "https://api.github.com/search/repositories?q=" + urllib.parse.quote(f"{query.strip()} {'fork:false' if not include_forks else ''} {'archived:false' if not include_archived else ''}".strip()),
                "note": "search query used for candidate discovery",
            }
            for query in active_queries
        ],
        "settings": {
            "limit": limit,
            "per_query": per_query,
            "include_forks": include_forks,
            "include_archived": include_archived,
            "fetch_readmes": fetch_readmes,
        },
        "summary": {
            "total_candidates": len(candidates),
            "selected": len(selected),
            "join": sum(1 for candidate in selected if candidate.recommendation == "join"),
            "watch": sum(1 for candidate in selected if candidate.recommendation == "watch"),
            "skip": sum(1 for candidate in selected if candidate.recommendation == "skip"),
        },
        "candidates": [candidate.to_dict() | {"issue_angles": issue_angles_for_repo(candidate)} for candidate in selected],
    }
    return bundle


def create_run_dir(output_root: Path = DEFAULT_OUTPUT_ROOT, *, timestamp: str | None = None) -> Path:
    stamp = (timestamp or utcnow_iso()).replace(":", "-")
    run_dir = output_root / safe_slug(stamp)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "repos").mkdir(exist_ok=True)
    (run_dir / "selected").mkdir(exist_ok=True)
    return run_dir


def render_candidate_block(candidate: dict[str, Any]) -> str:
    reasons = candidate.get("reasons", []) or []
    angles = candidate.get("issue_angles", []) or []
    topic_line = ", ".join(candidate.get("topics", []) or []) or "none"
    excerpt = candidate.get("readme_excerpt", "")
    signals = candidate.get("security_signals", []) or []
    signal_lines = [f"- {signal}" for signal in signals[:8]]
    likely_surface = candidate.get("likely_surface", []) or []

    lines = [
        f"Repo: {candidate.get('full_name', 'unknown')}",
        "",
        f"Why it is interesting: {candidate.get('description', '') or 'No description provided'}",
        f"Authorization state: {candidate.get('authorization_state', 'Public repo / no confirmed bounty scope')}",
        f"Suggested posture: {candidate.get('suggested_posture', 'Passive review only until scope is confirmed')}",
        f"Priority score: {candidate.get('priority_score', 0)}/100",
        f"Review state: {candidate.get('review_state', 'Needs scope confirmation')}",
        f"Repo URL: {candidate.get('html_url', '')}",
        "",
        "Likely surface:",
    ]
    if likely_surface:
        lines.extend(f"- {surface}" for surface in likely_surface)
    else:
        lines.append("- unknown")
    lines.extend([
        "",
        "Existing security signals:",
    ])
    if signal_lines:
        lines.extend(signal_lines)
    else:
        lines.append("- no signals")
    lines.extend([
        "",
        "Dependency manifests:",
    ])
    dependency_manifests = candidate.get("dependency_manifests", []) or []
    if dependency_manifests:
        lines.extend(f"- {manifest}" for manifest in dependency_manifests)
    else:
        lines.append("- none detected")
    lines.extend([
        "",
        f"Release cadence: {candidate.get('release_cadence', 'unknown')}",
        "",
        "Why it is interesting:",
        reasons[0] if reasons else (excerpt or "- no README excerpt available"),
        "",
        "Recommended next action:",
        "- Read contribution and security policy",
        "- Check bounty/scope",
        "- Run local static analysis only if authorized or clearly permitted",
    ])
    if angles:
        lines.extend(["", "Possible issue angles:"])
        lines.extend(f"- {angle}" for angle in angles)
    return "\n".join(lines) + "\n"


def render_summary(bundle: dict[str, Any], run_dir: Path | None = None) -> str:
    lines = [
        "# GitHub Discovery Bundle",
        "",
        f"- generated_at: `{bundle.get('generated_at', 'unknown')}`",
        f"- queries: `{'; '.join(bundle.get('queries', []) or [])}`",
        f"- selected: `{bundle.get('summary', {}).get('selected', 0)}`",
        f"- join: `{bundle.get('summary', {}).get('join', 0)}`",
        f"- watch: `{bundle.get('summary', {}).get('watch', 0)}`",
        f"- skip: `{bundle.get('summary', {}).get('skip', 0)}`",
        "",
        "| repo | priority | posture | stars | issues | language | surface |",
        "| --- | ---: | --- | ---: | ---: | --- | --- |",
    ]
    for candidate in bundle.get("candidates", []) or []:
        surface = ", ".join(candidate.get("likely_surface", []) or []) or "—"
        lines.append(
            "| {repo} | {score} | {rec} | {stars} | {issues} | {language} | {surface} |".format(
                repo=candidate.get("full_name", "unknown"),
                score=candidate.get("priority_score", 0),
                rec=candidate.get("suggested_posture", "watch"),
                stars=candidate.get("stars", 0),
                issues=candidate.get("open_issues", 0),
                language=candidate.get("language", "—") or "—",
                surface=surface,
            )
        )

    if run_dir is not None:
        lines.extend([
            "",
            "## Files",
            f"- bundle.json: `{display_path(run_dir / 'bundle.json')}`",
            f"- summary.md: `{display_path(run_dir / 'summary.md')}`",
            f"- repo notes: `{display_path(run_dir / 'repos')}`",
            f"- selected folder: `{display_path(run_dir / 'selected')}`",
        ])

    lines.extend([
        "",
        "Use the repo notes folder to decide what to join, what to watch, and what to turn into the next ANCHOR hunt.",
    ])
    return "\n".join(lines) + "\n"


def write_bundle(bundle: dict[str, Any], output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    run_dir = create_run_dir(output_root)
    (run_dir / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    (run_dir / "summary.md").write_text(render_summary(bundle, run_dir=run_dir), encoding="utf-8")

    for candidate in bundle.get("candidates", []) or []:
        repo_dir = run_dir / "repos" / safe_slug(str(candidate.get("full_name", "repo")))
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
        (repo_dir / "summary.md").write_text(render_candidate_block(candidate), encoding="utf-8")

    (run_dir / "README.md").write_text(
        "# GitHub Discovery Run\n\n"
        "This folder contains a curated repo-candidate bundle.\n\n"
        "- `bundle.json` is the machine-readable output.\n"
        "- `summary.md` is the compact human view.\n"
        "- `repos/` contains one folder per candidate with per-repo notes.\n"
        "- `selected/` is intentionally empty so you can copy the repos you want to pursue.\n",
        encoding="utf-8",
    )
    return run_dir


def list_discovery_runs(output_root: Path = DEFAULT_OUTPUT_ROOT) -> list[Path]:
    if not output_root.exists():
        return []
    runs = [path for path in output_root.iterdir() if path.is_dir()]
    runs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return runs


def find_latest_run(output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path | None:
    runs = list_discovery_runs(output_root)
    return runs[0] if runs else None


def load_bundle(run_dir: Path) -> dict[str, Any]:
    bundle_path = run_dir / "bundle.json"
    if not bundle_path.exists():
        raise GitHubDiscoveryError(f"Missing discovery bundle: {bundle_path}")
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GitHubDiscoveryError(f"Malformed discovery bundle: {bundle_path}")
    return data


def find_candidate(bundle: dict[str, Any], repo: str) -> dict[str, Any]:
    for candidate in bundle.get("candidates", []) or []:
        if isinstance(candidate, dict) and candidate.get("full_name") == repo:
            return candidate
    raise GitHubDiscoveryError(f"Repository not found in bundle: {repo}")


def slug_repo(repo: str) -> str:
    owner, _, name = repo.partition("/")
    if owner and name:
        return f"{safe_slug(owner)}-{safe_slug(name)}"
    return safe_slug(repo)


def copy_selection(
    candidate: dict[str, Any],
    run_dir: Path,
    selected_root: Path,
    *,
    selection_status: str = "human_approved",
    authorization_state: str = "scope_confirmation_required",
    next_action: str = "Review published scope and repository security policy before local analysis.",
) -> Path:
    repo = str(candidate.get("full_name", "")).strip()
    if not repo:
        raise GitHubDiscoveryError("Candidate is missing a repository name")
    selected_dir = selected_root / slug_repo(repo)
    selected_dir.mkdir(parents=True, exist_ok=True)
    (selected_dir / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    (selected_dir / "summary.md").write_text(render_candidate_block(candidate), encoding="utf-8")
    selection_record = {
        "schema_version": "1.0",
        "repo": repo,
        "selected_from_run": run_dir.name,
        "selected_at": utcnow_iso(),
        "selection_status": selection_status,
        "authorization_state": authorization_state,
        "next_action": next_action,
    }
    (selected_dir / "selection.json").write_text(json.dumps(selection_record, indent=2) + "\n", encoding="utf-8")
    return selected_dir


def run_github_discovery(
    queries: Iterable[str] | None = None,
    *,
    limit: int = 12,
    per_query: int = 25,
    include_forks: bool = False,
    include_archived: bool = False,
    fetch_readmes: bool = True,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[dict[str, Any], Path]:
    bundle = discover_repositories(
        queries,
        limit=limit,
        per_query=per_query,
        include_forks=include_forks,
        include_archived=include_archived,
        fetch_readmes=fetch_readmes,
    )
    run_dir = write_bundle(bundle, output_root=output_root)
    return bundle, run_dir


def select_repo_from_latest_bundle(
    repo: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    selection_status: str = "human_approved",
    authorization_state: str = "scope_confirmation_required",
    next_action: str = "Review published scope and repository security policy before local analysis.",
) -> tuple[Path, Path]:
    run_dir = find_latest_run(output_root)
    if run_dir is None:
        raise GitHubDiscoveryError("No discovery runs available")
    bundle = load_bundle(run_dir)
    candidate = find_candidate(bundle, repo)
    selected_dir = copy_selection(
        candidate,
        run_dir,
        run_dir / "selected",
        selection_status=selection_status,
        authorization_state=authorization_state,
        next_action=next_action,
    )
    return run_dir, selected_dir


def load_selection(selected_dir: Path) -> dict[str, Any]:
    selection_path = selected_dir / "selection.json"
    if not selection_path.exists():
        raise GitHubDiscoveryError(f"Missing selection record: {selection_path}")
    data = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GitHubDiscoveryError(f"Malformed selection record: {selection_path}")
    return data


def find_selected_repo_dir(
    repo: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
) -> tuple[Path, Path]:
    repo = repo.strip()
    if not repo:
        raise GitHubDiscoveryError("Repository name is required")

    if run_id:
        run_dir = output_root / run_id
        selected_dir = run_dir / "selected" / slug_repo(repo)
        selection_path = selected_dir / "selection.json"
        if not selection_path.exists():
            raise GitHubDiscoveryError(f"Selected repo not found for run {run_id}: {repo}")
        selection = load_selection(selected_dir)
        if str(selection.get("repo", "")).strip() != repo:
            raise GitHubDiscoveryError(f"Selected repo record does not match requested repo: {repo}")
        return run_dir, selected_dir

    for run_dir in list_discovery_runs(output_root):
        selected_dir = run_dir / "selected" / slug_repo(repo)
        selection_path = selected_dir / "selection.json"
        if not selection_path.exists():
            continue
        selection = load_selection(selected_dir)
        if str(selection.get("repo", "")).strip() == repo:
            return run_dir, selected_dir
    raise GitHubDiscoveryError(f"Selected repo not found in any discovery run: {repo}")


def _selected_repo_focus(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    issue_angles = [str(item) for item in (candidate.get("issue_angles", []) or []) if item]
    likely_surface = [str(item) for item in (candidate.get("likely_surface", []) or []) if item]
    focus: list[dict[str, Any]] = []

    if any("invariant" in angle.lower() or "fuzz" in angle.lower() for angle in issue_angles + likely_surface):
        focus.append(
            {
                "name": "Invariant and fuzz harness review",
                "why": "The selected repo already signals test-generation or property-based coverage, so the first plan should stay on harness quality and property shape.",
                "signals": [
                    "property names and failure classes are visible in docs or examples",
                    "harnesses exist but may not cover the named edge case",
                    "machine-readable output could make CI easier",
                ],
                "tests": [
                    "List the existing harness entry points and property names.",
                    "Identify one minimal reproduction path for the selected edge case.",
                    "Confirm the candidate is a planning target only until scope is rechecked.",
                ],
            }
        )
    if any("doc" in angle.lower() or "workflow" in angle.lower() for angle in issue_angles + likely_surface):
        focus.append(
            {
                "name": "Docs and workflow boundary review",
                "why": "The selected repo looks like it would benefit from a sharper explanation of how the workflow is meant to be used.",
                "signals": [
                    "README or docs omit the exact boundary between planning and analysis",
                    "examples exist but need a clearer invocation path",
                    "workflow outputs may not be easy to consume in CI",
                ],
                "tests": [
                    "Read the current docs entry points before planning any analysis.",
                    "Extract the exact user-facing workflow described by the repo.",
                    "Keep the next action limited to scope confirmation.",
                ],
            }
        )
    if any("regression" in angle.lower() or "artifact" in angle.lower() or "output" in angle.lower() for angle in issue_angles + likely_surface):
        focus.append(
            {
                "name": "Regression artifact review",
                "why": "The selected repo may benefit from more stable output for CI or bot integration.",
                "signals": [
                    "summary output is human-only",
                    "fixtures or snapshots exist",
                    "downstream tooling could break on wording changes",
                ],
                "tests": [
                    "Identify the output surface that downstream tooling consumes.",
                    "Check whether the repo already has fixtures or golden files.",
                    "Do not move from planning into execution until the scope is confirmed.",
                ],
            }
        )

    if not focus:
        focus.append(
            {
                "name": "Scope-first call-path review",
                "why": "No narrow issue angle stood out, so keep the hunt plan limited to the approved repo boundary and a single falsifiable path.",
                "signals": [
                    "selected repo is human-approved for planning only",
                    "candidate evidence exists in the discovery bundle",
                    "the next step is to confirm published scope",
                ],
                "tests": [
                    "Read the selection record and published scope before any analysis.",
                    "Pick one narrow path from the candidate evidence.",
                    "Stop if the path is outside the approved posture.",
                ],
            }
        )

    return focus[:3]


def build_selected_repo_hunt_plan(
    selected_dir: Path,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    candidate_path = selected_dir / "candidate.json"
    summary_path = selected_dir / "summary.md"
    selection_path = selected_dir / "selection.json"
    if not candidate_path.exists():
        raise GitHubDiscoveryError(f"Missing candidate record: {candidate_path}")
    if not summary_path.exists():
        raise GitHubDiscoveryError(f"Missing candidate summary: {summary_path}")
    if not selection_path.exists():
        raise GitHubDiscoveryError(f"Missing selection record: {selection_path}")

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    selection = load_selection(selected_dir)
    if not isinstance(candidate, dict):
        raise GitHubDiscoveryError(f"Malformed candidate record: {candidate_path}")

    repo = str(candidate.get("full_name", "")).strip()
    if not repo or str(selection.get("repo", "")).strip() != repo:
        raise GitHubDiscoveryError("Selected repo and candidate record do not match")

    issue_angles = [str(item) for item in (candidate.get("issue_angles", []) or []) if item]
    if not issue_angles:
        issue_angles = issue_angles_for_repo(RepoCandidate(
            full_name=repo,
            html_url=str(candidate.get("html_url", "")),
            description=str(candidate.get("description", "")),
            stars=int(candidate.get("stars") or 0),
            forks=int(candidate.get("forks") or 0),
            open_issues=int(candidate.get("open_issues") or 0),
            pushed_at=str(candidate.get("pushed_at", "")),
            updated_at=str(candidate.get("updated_at", "")),
            archived=bool(candidate.get("archived")),
            fork=bool(candidate.get("fork")),
            language=str(candidate.get("language", "")),
            topics=[str(topic) for topic in (candidate.get("topics") or []) if topic],
            docs_present=bool(candidate.get("docs_present")),
            readme_excerpt=str(candidate.get("readme_excerpt", "")),
            priority_score=int(candidate.get("priority_score") or 0),
        ))

    focus = _selected_repo_focus(candidate)
    selected_repo = {
        "full_name": repo,
        "html_url": str(candidate.get("html_url", "")),
        "language": str(candidate.get("language", "")),
        "priority_score": int(candidate.get("priority_score") or 0),
        "review_state": str(candidate.get("review_state", "Needs scope confirmation") or "Needs scope confirmation"),
        "suggested_posture": str(candidate.get("suggested_posture", "Passive review only until scope is confirmed") or "Passive review only until scope is confirmed"),
        "authorization_state": str(candidate.get("authorization_state", "Public repo / no confirmed bounty scope") or "Public repo / no confirmed bounty scope"),
        "issue_angles": issue_angles,
        "likely_surface": [str(item) for item in (candidate.get("likely_surface", []) or []) if item],
        "security_signals": [str(item) for item in (candidate.get("security_signals", []) or []) if item],
        "evidence_sources": [dict(item) for item in (candidate.get("evidence_sources", []) or []) if isinstance(item, dict)],
    }

    hypothesis_templates = []
    for item in focus:
        if "Docs" in item["name"]:
            claim = f"I think `{repo}` needs a clearer docs boundary because the current candidate evidence points to an analysis workflow that is easy to misuse."
            falsifier = "If the docs already state the planning boundary and next action clearly, the hypothesis dies."
        elif "Regression" in item["name"]:
            claim = f"I think `{repo}` has a fragile output surface because the selected candidate evidence suggests downstream tooling may depend on stable text or artifacts."
            falsifier = "If the output is already machine-readable or covered by golden tests, the hypothesis dies."
        elif "Invariant" in item["name"]:
            claim = f"I think `{repo}` can benefit from a tighter invariant or fuzz harness because the selected candidate evidence points at property-based testing as the primary surface."
            falsifier = "If the repo already has a complete, minimal invariant harness for the named failure class, the hypothesis dies."
        else:
            claim = f"I think `{repo}` has a narrow, scopeable issue surface that can be reduced to one falsifiable path."
            falsifier = "If the path cannot be grounded in the selected evidence or is outside scope, the hypothesis dies."
        hypothesis_templates.append({"mechanism": item["name"], "claim": claim, "falsifier": falsifier})

    payload = {
        "schema_version": "1.0",
        "source": "github_discovery.build_selected_repo_hunt_plan",
        "selected_repo": selected_repo,
        "selection": {
            "repo": repo,
            "selected_from_run": str(selection.get("selected_from_run", run_dir_name_from_selected_dir(selected_dir))),
            "selected_at": str(selection.get("selected_at", "")),
            "selection_status": str(selection.get("selection_status", "human_approved")),
            "authorization_state": str(selection.get("authorization_state", "scope_confirmation_required")),
            "next_action": str(selection.get("next_action", "Review published scope and repository security policy before local analysis.")),
        },
        "objective": (
            f"Confirm published scope for `{repo}` and turn the selected repo into a single, falsifiable hunt plan without exceeding approval to plan."
        ),
        "hunt_for": issue_angles[:3] or [
            "scope confirmation",
            "minimal reproducible path",
            "evidence-backed plan only",
        ],
        "scope_checklist": [
            "Confirm the published scope or repository policy before any local analysis.",
            "Keep the current step limited to planning and evidence review.",
            "Do not clone, scan, open issues, draft PRs, or contact maintainers yet.",
        ],
        "scope_limits": [
            "No intrusive testing.",
            "No automated contact.",
            "No issue or PR creation.",
            "No production or private asset interaction.",
        ],
        "focus": focus,
        "hypothesis_templates": hypothesis_templates,
        "baseline_process": [
            {"step": "Selection review", "goal": "Read the immutable selection record and the candidate brief before planning any analysis."},
            {"step": "Scope confirmation", "goal": "Check the published scope and repo security policy to determine whether analysis is allowed."},
            {"step": "Surface mapping", "goal": "Map the named issue angles to one narrow path and one minimal hypothesis."},
            {"step": "Evidence-only planning", "goal": "Write down the claims, falsifiers, and source links without running any tests yet."},
            {"step": "Human gate", "goal": "Stop and request approval before any local clone, test, or harness work."},
        ],
        "evidence_requirements": [
            "The selected candidate brief and selection record stay unchanged.",
            "Every meaningful claim points back to candidate.json, summary.md, or selection.json.",
            "The plan must make the authorization boundary explicit.",
            "No reproduction step should be attempted before scope confirmation.",
        ],
        "falsifiers": [
            "The repo is outside published scope or the security policy disallows analysis.",
            "The candidate evidence does not support the named issue angle.",
            "The repo already has a complete, stable harness for the chosen surface.",
            "The issue path requires intrusive or unauthorized behavior.",
        ],
        "next_actions": [
            "Review the published scope and repository security policy.",
            "Choose one narrow hypothesis from the selected candidate brief.",
            "Keep the next step as a plan artifact only.",
            "Escalate to local analysis only after human confirmation.",
        ],
        "source_refs": {
            "candidate_json": str(candidate_path.relative_to(root)) if candidate_path.is_relative_to(root) else str(candidate_path),
            "summary_md": str(summary_path.relative_to(root)) if summary_path.is_relative_to(root) else str(summary_path),
            "selection_json": str(selection_path.relative_to(root)) if selection_path.is_relative_to(root) else str(selection_path),
            "selected_dir": str(selected_dir.relative_to(root)) if selected_dir.is_relative_to(root) else str(selected_dir),
        },
    }
    return payload


def render_scope_confirmation_template(candidate: dict[str, Any], selection: dict[str, Any]) -> str:
    repo = str(candidate.get("full_name", selection.get("repo", "unknown/unknown"))).strip()
    selected_from_run = str(selection.get("selected_from_run", ""))
    selected_at = str(selection.get("selected_at", ""))
    source_url = str(candidate.get("html_url", "")).strip()
    return (
        "# Scope Confirmation\n\n"
        f"- Repo: `{repo}`\n"
        f"- Selected from run: `{selected_from_run}`\n"
        f"- Selected at: `{selected_at}`\n"
        "\n"
        "## Published scope or security policy\n"
        "- Source URL: \n"
        "- Notes: \n"
        "\n"
        "## In-scope assets / commit\n"
        "- Repo / asset list: \n"
        "- Commit / tag / release: \n"
        "\n"
        "## Permitted testing methods\n"
        "- \n"
        "\n"
        "## Prohibited actions\n"
        "- \n"
        "\n"
        "## Disclosure / reporting channel\n"
        "- \n"
        "\n"
        "## Date checked\n"
        "- \n"
        "\n"
        "## Reviewer decision\n"
        "reviewer_decision: \n"
        "- `authorized`\n"
        "- `not authorized`\n"
        "- `unclear`\n"
        "\n"
        "## Reviewer notes\n"
        "- \n"
        "\n"
        "## Discovery source reference\n"
        f"- Candidate URL: `{source_url}`\n"
    )


def parse_scope_decision(text: str) -> str:
    patterns = [
        r"(?im)^\s*(?:[-*]\s*)?reviewer_decision\s*:\s*(authorized|not authorized|unclear)\s*$",
        r"(?im)^\s*(?:[-*]\s*)?reviewer decision\s*:\s*(authorized|not authorized|unclear)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip().lower()
    match = re.search(r"(?im)^\s*-\s*`?(authorized|not authorized|unclear)`?\s*$", text)
    if match:
        return match.group(1).strip().lower()
    return "unclear"


def evaluate_scope_confirmation(selected_dir: Path) -> dict[str, Any]:
    scope_path = selected_dir / "scope_confirmation.md"
    if not scope_path.exists():
        return {
            "scope_status": "NOT AUTHORIZED",
            "reason": "scope_confirmation.md is missing",
            "allowed_actions": "planning only",
            "reviewer_decision": "unclear",
            "scope_file": str(scope_path),
        }
    text = scope_path.read_text(encoding="utf-8")
    decision = parse_scope_decision(text)
    status = "AUTHORIZED" if decision == "authorized" else "NOT AUTHORIZED"
    reason = "reviewer_decision is authorized" if decision == "authorized" else f"reviewer_decision is {decision}"
    allowed_actions = "planning and authorized analysis" if decision == "authorized" else "planning only"
    return {
        "scope_status": status,
        "reason": reason,
        "allowed_actions": allowed_actions,
        "reviewer_decision": decision,
        "scope_file": str(scope_path),
    }


def ensure_scope_confirmation(selected_dir: Path) -> Path:
    candidate_path = selected_dir / "candidate.json"
    selection_path = selected_dir / "selection.json"
    if not candidate_path.exists():
        raise GitHubDiscoveryError(f"Missing candidate record: {candidate_path}")
    if not selection_path.exists():
        raise GitHubDiscoveryError(f"Missing selection record: {selection_path}")
    scope_path = selected_dir / "scope_confirmation.md"
    if scope_path.exists():
        return scope_path
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    selection = load_selection(selected_dir)
    if not isinstance(candidate, dict):
        raise GitHubDiscoveryError(f"Malformed candidate record: {candidate_path}")
    scope_path.write_text(render_scope_confirmation_template(candidate, selection), encoding="utf-8")
    return scope_path


def require_authorized_scope(selected_dir: Path) -> dict[str, Any]:
    scope = evaluate_scope_confirmation(selected_dir)
    if scope["reviewer_decision"] != "authorized":
        raise GitHubDiscoveryError(
            f"Scope status: {scope['scope_status']}\nReason: {scope['reason']}\nAllowed actions: {scope['allowed_actions']}"
        )
    return scope


def check_selected_repo_scope(
    repo: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    run_dir, selected_dir = find_selected_repo_dir(repo, output_root=output_root, run_id=run_id)
    scope = evaluate_scope_confirmation(selected_dir)
    return run_dir, selected_dir, scope


def run_selected_repo_hunt_plan(
    repo: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    from hunt_planner import render_hunt_plan

    run_dir, selected_dir = find_selected_repo_dir(repo, output_root=output_root, run_id=run_id)
    ensure_scope_confirmation(selected_dir)
    scope = evaluate_scope_confirmation(selected_dir)
    payload = build_selected_repo_hunt_plan(selected_dir)
    payload["scope_confirmation"] = scope
    (selected_dir / "hunt_plan.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (selected_dir / "hunt_plan.md").write_text(render_hunt_plan(payload), encoding="utf-8")
    return payload, run_dir, selected_dir


def run_dir_name_from_selected_dir(selected_dir: Path) -> str:
    return selected_dir.parent.parent.name if selected_dir.parent.parent else selected_dir.parent.name
