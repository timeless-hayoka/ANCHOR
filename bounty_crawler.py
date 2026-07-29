"""Automated bounty crawler for discovering smart contract bugs.

This crawler discovers security-relevant GitHub repositories and issues,
validates scope authorization, and generates Trinity leads for hunting.

Usage:
    python bounty_crawler.py --org solana --limit 50
    python bounty_crawler.py --token $GITHUB_TOKEN --profile auth --scope-check
    python bounty_crawler.py --crawl-mode all --output leads.jsonl
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

from bugbot.scope import (
    ScopeNotAuthorizedError,
    default_scope_dir,
    current_scope_state,
    ScopeState,
)
from trinity_lead_state_machine import (
    LeadRecord,
    SCHEMA_VERSION,
    utcnow_iso,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT / "discoveries" / "crawler"
GITHUB_API_BASE = "https://api.github.com"

CRAWLER_KEYWORDS = {
    "security": [
        "security vulnerability",
        "smart contract audit",
        "bug bounty",
    ],
    "auth": [
        "access control",
        "permission boundary",
        "authorization check",
    ],
    "accounting": [
        "accounting invariant",
        "balance tracking",
        "rounding error",
    ],
    "oracle": [
        "oracle price feed",
        "stale price",
        "price manipulation",
    ],
    "upgrade": [
        "proxy vulnerability",
        "initialization bug",
        "upgradeable contract",
    ],
}


@dataclass
class GitHubRepo:
    """Discovered GitHub repository."""
    owner: str
    name: str
    url: str
    description: str = ""
    stars: int = 0
    language: str = ""
    topics: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class GitHubIssue:
    """GitHub issue potentially containing bug signals."""
    repo: GitHubRepo
    number: int
    title: str
    body: str
    author: str
    created_at: str
    url: str
    labels: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash((self.repo.full_name, self.number))


class GitHubClient:
    """Minimal GitHub API client for bounty discovery."""

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.rate_limit_remaining = 60
        self.rate_limit_reset = 0

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Execute GitHub API request with rate limiting."""
        if self.rate_limit_remaining <= 1:
            wait_time = max(0, self.rate_limit_reset - int(time.time())) + 1
            logger.warning(f"Rate limit approaching, waiting {wait_time}s")
            time.sleep(wait_time)

        url = f"{GITHUB_API_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        req = urllib.request.Request(url, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                self.rate_limit_remaining = int(
                    response.headers.get("X-RateLimit-Remaining", "60")
                )
                self.rate_limit_reset = int(
                    response.headers.get("X-RateLimit-Reset", "0")
                )
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.warning("Rate limited or forbidden")
                return {} if method == "GET" else []
            if e.code == 404:
                return {} if method == "GET" else []
            raise

    def search_repos(
        self,
        query: str,
        language: str = "solidity",
        limit: int = 10,
    ) -> list[GitHubRepo]:
        """Search for repositories matching query."""
        search_query = f"{query} language:{language}"
        params = {
            "q": search_query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100),
        }

        result = self._request("GET", "/search/repositories", params)
        repos = []

        if isinstance(result, dict) and "items" in result:
            for item in result["items"][:limit]:
                repo = GitHubRepo(
                    owner=item["owner"]["login"],
                    name=item["name"],
                    url=item["html_url"],
                    description=item.get("description", ""),
                    stars=item.get("stargazers_count", 0),
                    language=item.get("language", ""),
                    topics=item.get("topics", []),
                )
                repos.append(repo)

        return repos

    def get_issues(
        self,
        owner: str,
        repo: str,
        limit: int = 50,
        state: str = "open",
    ) -> list[GitHubIssue]:
        """Fetch issues from a repository."""
        path = f"/repos/{owner}/{repo}/issues"
        params = {
            "state": state,
            "per_page": min(limit, 100),
            "sort": "updated",
            "direction": "desc",
        }

        result = self._request("GET", path, params)
        issues = []

        if isinstance(result, list):
            for item in result[:limit]:
                issue = GitHubIssue(
                    repo=GitHubRepo(owner=owner, name=repo, url=""),
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body", ""),
                    author=item["user"]["login"],
                    created_at=item["created_at"],
                    url=item["html_url"],
                    labels=[label["name"] for label in item.get("labels", [])],
                )
                issues.append(issue)

        return issues

    def get_repo_details(self, owner: str, name: str) -> GitHubRepo | None:
        """Fetch detailed repository information."""
        path = f"/repos/{owner}/{name}"
        result = self._request("GET", path)

        if isinstance(result, dict) and "id" in result:
            return GitHubRepo(
                owner=result["owner"]["login"],
                name=result["name"],
                url=result["html_url"],
                description=result.get("description", ""),
                stars=result.get("stargazers_count", 0),
                language=result.get("language", ""),
                topics=result.get("topics", []),
            )
        return None


class BugSignalExtractor:
    """Extract potential bug signals from GitHub content."""

    # Regex patterns for common bug signals
    PATTERNS = {
        "reentrancy": re.compile(
            r"reentran|callback|external call|delegatecall", re.I
        ),
        "access_control": re.compile(
            r"access control|permission|authorization|owner|role", re.I
        ),
        "accounting": re.compile(
            r"balance.*track|accounting|rounding|precision|dust", re.I
        ),
        "oracle": re.compile(r"oracle|price feed|stale|manipulation", re.I),
        "initialization": re.compile(r"initializer|init.*twice|double.*init", re.I),
        "upgrade": re.compile(r"proxy|upgrade|implementation", re.I),
        "overflow": re.compile(r"overflow|underflow|unchecked", re.I),
    }

    SEVERITY_KEYWORDS = {
        "critical": re.compile(r"critical|severe|exploitable|leaked|stolen", re.I),
        "high": re.compile(r"high|significant|substantial", re.I),
        "medium": re.compile(r"medium|moderate|notable", re.I),
    }

    @classmethod
    def extract_signals(cls, title: str, body: str) -> dict[str, Any]:
        """Extract bug signals from issue title and body."""
        text = f"{title} {body}".lower()
        signals = []
        categories = []

        for category, pattern in cls.PATTERNS.items():
            if pattern.search(text):
                categories.append(category)
                signals.append(category)

        severity = "low"
        for level, pattern in cls.SEVERITY_KEYWORDS.items():
            if pattern.search(text):
                severity = level
                break

        return {
            "categories": categories,
            "signals": signals,
            "severity": severity,
            "score": len(signals) * 10 + ({"critical": 30, "high": 20, "medium": 10}.get(severity, 0)),
        }

    @classmethod
    def is_relevant(cls, issue: GitHubIssue) -> bool:
        """Determine if an issue is relevant for bug hunting."""
        signals = cls.extract_signals(issue.title, issue.body)

        # Issue is relevant if it has multiple signals or high/critical severity
        if len(signals["signals"]) >= 2:
            return True
        if signals["severity"] in ("critical", "high"):
            return True
        if signals["score"] >= 20:
            return True

        return False


def create_lead_from_issue(
    issue: GitHubIssue,
    profile: str = "auth",
) -> LeadRecord:
    """Convert GitHub issue to Trinity lead record."""
    signals = BugSignalExtractor.extract_signals(issue.title, issue.body)

    lead_id = f"lead_{issue.repo.full_name.replace('/', '_')}_{issue.number}"

    claim = (
        f"GitHub issue #{issue.number} on {issue.repo.full_name} suggests "
        f"a potential {profile} vulnerability: {issue.title}"
    )

    scope = f"Target: {issue.repo.full_name}. Authorized scope status unknown; "
    scope += f"scope must be verified before analysis. Repository at {issue.repo.url}."

    repro_plan = (
        f"1. Verify authorization for {issue.repo.full_name}\n"
        f"2. Clone the repository and review the issue context\n"
        f"3. Identify the affected code path\n"
        f"4. Develop a minimal reproduction in Foundry or similar harness\n"
        f"5. Execute the reproduction and verify impact"
    )

    return LeadRecord(
        lead_id=lead_id,
        target=issue.repo.full_name,
        title=f"{issue.title} ({issue.repo.full_name})",
        state="signal",
        scope_status="unknown",
        claim=claim,
        scope=scope,
        mechanism=issue.body[:500] if issue.body else "",
        falsifier="If the code already contains the fix or mitigation, or if the issue was closed as not-a-bug.",
        repro_plan=repro_plan,
        impact_boundary="",
        evidence_refs=[issue.url],
        review_refs=[],
        created_at=utcnow_iso(),
        updated_at=utcnow_iso(),
        events=[],
    )


class BountyCrawler:
    """Main bounty discovery crawler."""

    def __init__(
        self,
        token: str | None = None,
        scope_dir: Path | None = None,
        output_dir: Path | None = None,
    ):
        self.client = GitHubClient(token)
        self.scope_dir = scope_dir or default_scope_dir()
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.discovered_issues: set[GitHubIssue] = set()

    def crawl_keyword_profile(
        self,
        profile: str,
        limit: int = 20,
        scope_check: bool = False,
    ) -> list[GitHubIssue]:
        """Crawl repositories for a given bug profile."""
        logger.info(f"Crawling {profile} profile")
        relevant_issues = []

        keywords = CRAWLER_KEYWORDS.get(profile, [])
        if not keywords:
            logger.warning(f"Unknown profile: {profile}")
            return []

        for keyword in keywords:
            logger.info(f"  Searching: {keyword}")
            repos = self.client.search_repos(keyword, limit=5)

            for repo in repos:
                logger.debug(f"    Found repo: {repo.full_name} ({repo.stars} stars)")

                if scope_check:
                    scope_state = current_scope_state(self.scope_dir)
                    if not scope_state.authorized or scope_state.target_id != repo.full_name:
                        logger.debug(f"      Skipped (not authorized for {repo.full_name})")
                        continue

                issues = self.client.get_issues(repo.owner, repo.name, limit=10)
                for issue in issues:
                    if BugSignalExtractor.is_relevant(issue):
                        relevant_issues.append(issue)
                        logger.info(
                            f"      Found signal: {issue.title[:50]}... "
                            f"(score: {BugSignalExtractor.extract_signals(issue.title, issue.body)['score']})"
                        )

            time.sleep(1)  # Rate limit courtesy

        return relevant_issues

    def crawl_organization(
        self,
        org: str,
        limit: int = 50,
        scope_check: bool = False,
    ) -> list[GitHubIssue]:
        """Crawl all repositories in an organization."""
        logger.info(f"Crawling organization: {org}")
        relevant_issues = []

        # Fetch repos from organization
        path = f"/orgs/{org}/repos"
        params = {
            "type": "public",
            "sort": "stars",
            "per_page": min(limit, 100),
        }

        result = self.client._request("GET", path, params)
        if not isinstance(result, list):
            logger.error(f"Failed to fetch repos from {org}")
            return []

        for item in result[:limit]:
            repo = GitHubRepo(
                owner=item["owner"]["login"],
                name=item["name"],
                url=item["html_url"],
                description=item.get("description", ""),
                stars=item.get("stargazers_count", 0),
                language=item.get("language", ""),
                topics=item.get("topics", []),
            )

            if scope_check:
                scope_state = current_scope_state(self.scope_dir)
                if not scope_state.authorized or scope_state.target_id != repo.full_name:
                    logger.debug(f"  {repo.full_name}: not authorized")
                    continue

            issues = self.client.get_issues(repo.owner, repo.name, limit=10)
            for issue in issues:
                if BugSignalExtractor.is_relevant(issue):
                    relevant_issues.append(issue)
                    signals = BugSignalExtractor.extract_signals(
                        issue.title, issue.body
                    )
                    logger.info(
                        f"  Signal found: {issue.title[:40]}... "
                        f"({', '.join(signals['categories'][:2])})"
                    )

            time.sleep(0.5)

        return relevant_issues

    def generate_leads(
        self,
        issues: list[GitHubIssue],
        profile: str = "auth",
    ) -> list[LeadRecord]:
        """Convert discovered issues to Trinity leads."""
        leads = []
        for issue in issues:
            lead = create_lead_from_issue(issue, profile)
            leads.append(lead)
        return leads

    def save_leads(
        self,
        leads: list[LeadRecord],
        output_file: str | None = None,
    ) -> Path:
        """Save leads to JSONL file."""
        if not output_file:
            timestamp = dt.datetime.now().isoformat()[:10]
            output_file = f"crawl_{timestamp}.jsonl"

        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            for lead in leads:
                f.write(json.dumps(lead.to_dict()) + "\n")

        logger.info(f"Saved {len(leads)} leads to {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Bounty crawler for discovering smart contract bugs",
    )
    parser.add_argument(
        "--token",
        help="GitHub API token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--profile",
        choices=list(CRAWLER_KEYWORDS.keys()),
        default="auth",
        help="Bug hunting profile to search for",
    )
    parser.add_argument(
        "--org",
        help="Crawl a specific GitHub organization",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results to fetch per query",
    )
    parser.add_argument(
        "--scope-check",
        action="store_true",
        help="Only include leads for authorized targets (requires scope grants)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for discovered leads",
    )
    parser.add_argument(
        "--output-file",
        help="Output filename (default: crawl_YYYY-MM-DD.jsonl)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    crawler = BountyCrawler(
        token=args.token,
        output_dir=args.output_dir,
    )

    if args.org:
        issues = crawler.crawl_organization(
            args.org,
            limit=args.limit,
            scope_check=args.scope_check,
        )
    else:
        issues = crawler.crawl_keyword_profile(
            args.profile,
            limit=args.limit,
            scope_check=args.scope_check,
        )

    leads = crawler.generate_leads(issues, profile=args.profile)
    output_path = crawler.save_leads(leads, output_file=args.output_file)

    print(f"\nDiscovered {len(leads)} potential bug leads")
    print(f"Saved to: {output_path}")
    print(f"\nNext steps:")
    print(f"1. Review leads in the output file")
    print(f"2. Use 'anchor lead show <lead_id>' to inspect individual leads")
    print(f"3. For authorized targets, run 'anchor hunt <lead_id>' to begin analysis")


if __name__ == "__main__":
    main()
