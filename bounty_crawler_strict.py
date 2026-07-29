"""Strict bounty crawler: Only finds ACTUAL authorized bounty programs.

CRITICAL DESIGN PRINCIPLE:
A GitHub repository mentioning "audit" or "security" is NOT authorized.
Authorization requires explicit bounty program evidence from official sources.

Only these count as authorization:
  - Immunefi program URL in README or docs
  - HackerOne program page
  - Code4rena contest link
  - Sherlock protocol page
  - Cantina audit marketplace
  - CodeHawks contest
  - Official project bounty announcement

Anything else = UNCONFIRMED (not authorized).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DISCOVERIES_DIR = ROOT / "discoveries" / "crawler"


class AuthorizationState(StrEnum):
    """Authorization lifecycle states."""
    UNCONFIRMED = "unconfirmed"                         # Public repo, no bounty evidence
    PUBLIC_REVIEW_ONLY = "public_review_only"           # Code audit writeups, not a bounty
    PROGRAM_FOUND_UNMATCHED = "program_found_unmatched" # Bounty exists, but repo doesn't match
    AUTHORIZED_ASSET_MATCHED = "authorized_asset_matched"  # ✓ Asset explicitly in scope
    EXPIRED_OR_ARCHIVED = "expired_or_archived"         # Program closed or contest ended
    CONTRADICTED = "contradicted"                       # "No bounty" or educational disclaimer


@dataclass(frozen=True)
class AuthorizationEvidence:
    """Proof of bounty program authorization."""
    bounty_url: str                                     # Where did we find the program?
    program_name: str                                   # Immunefi, Code4rena, etc.
    asset_type: str                                     # "contract", "repository", "domain"
    asset_identifier: str                               # Address, repo URL, domain
    found_in: str                                        # Where in repo (README, docs, etc.)
    confidence: float                                   # 0.0-1.0 (how sure are we?)


@dataclass
class CrawlResult:
    """Result of scanning a GitHub repository."""
    repo_owner: str
    repo_name: str
    repo_url: str
    state: AuthorizationState

    # Scoring breakdown
    technical_interest_score: float = 0.0              # Does code look promising? (0-100)
    authorization_confidence: float = 0.0              # How sure is bounty authorization? (0-1.0)
    bounty_value_score: float = 0.0                    # Estimated payout? (0-100)

    evidence: list[AuthorizationEvidence] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)  # Reasons to reject
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_authorized(self) -> bool:
        """Only AUTHORIZED_ASSET_MATCHED is safe to hunt."""
        return self.state == AuthorizationState.AUTHORIZED_ASSET_MATCHED


class BountyProgramDetector:
    """Detects actual bounty program evidence in repositories."""

    # Official bounty platform URL patterns
    BOUNTY_PROGRAM_PATTERNS = {
        "immunefi": re.compile(
            r"https://immunefi\.com/(bug-bounty|bounties)/[\w\-]+", re.I
        ),
        "hackerone": re.compile(
            r"https://hackerone\.com/[\w\-]+", re.I
        ),
        "code4rena": re.compile(
            r"https://code4rena\.com/contests/[\w\-]+", re.I
        ),
        "sherlock": re.compile(
            r"https://sherlock\.xyz/competitions/[\w\-]+", re.I
        ),
        "cantina": re.compile(
            r"https://cantina\.xyz/(competitions|audits)/[\w\-]+", re.I
        ),
        "codehawks": re.compile(
            r"https://codehawks\.com/(competitions|audits)/[\w\-]+", re.I
        ),
    }

    # Negative signals that BLOCK authorization
    REJECT_PATTERNS = {
        "educational": re.compile(r"educational|practice|learning|demo|example", re.I),
        "no_bounty": re.compile(r"no bounty|not for bounty|bounty not active", re.I),
        "archived": re.compile(r"archived|deprecated|deprecated|no longer maintained", re.I),
        "audit_planned": re.compile(r"audit\s+(?:is\s+)?planned|planned audit|pending audit|waiting for audit", re.I),
        "not_audited": re.compile(r"not audited|unaudited", re.I),
        "mainnet_blocked": re.compile(r"mainnet blocked|production blocked", re.I),
        "writeup": re.compile(r"security writeup|post-mortem|postmortem|incident report", re.I),
    }

    @classmethod
    def detect_bounty_programs(cls, readme_content: str, repo_url: str) -> list[AuthorizationEvidence]:
        """Find actual bounty program evidence in README."""
        evidence = []

        for platform, pattern in cls.BOUNTY_PROGRAM_PATTERNS.items():
            matches = pattern.finditer(readme_content)
            for match in matches:
                evidence.append(
                    AuthorizationEvidence(
                        bounty_url=match.group(0),
                        program_name=platform.capitalize(),
                        asset_type="repository",
                        asset_identifier=repo_url,
                        found_in="README",
                        confidence=0.9,  # High confidence - explicit link
                    )
                )

        return evidence

    @classmethod
    def detect_negative_signals(cls, readme_content: str, description: str = "") -> list[str]:
        """Find signals that contradict bounty authorization."""
        text = f"{readme_content} {description}".lower()
        signals = []

        for signal_name, pattern in cls.REJECT_PATTERNS.items():
            if pattern.search(text):
                signals.append(signal_name)

        return signals

    @classmethod
    def classify_authorization(
        cls,
        repo_owner: str,
        repo_name: str,
        readme_content: str,
        description: str,
    ) -> CrawlResult:
        """Classify repository's authorization state."""
        repo_url = f"https://github.com/{repo_owner}/{repo_name}"

        # Detect bounty programs
        evidence = cls.detect_bounty_programs(readme_content, repo_url)

        # Detect negative signals
        negative_signals = cls.detect_negative_signals(readme_content, description)

        # Determine state
        if negative_signals:
            state = AuthorizationState.CONTRADICTED
        elif evidence:
            state = AuthorizationState.AUTHORIZED_ASSET_MATCHED
        else:
            state = AuthorizationState.UNCONFIRMED

        return CrawlResult(
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_url=repo_url,
            state=state,
            evidence=evidence,
            negative_signals=negative_signals,
            authorization_confidence=0.9 if (evidence and not negative_signals) else 0.0,
        )


class StrictBountyCrawler:
    """Conservative crawler: only authorizes programs with explicit bounty evidence."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or DISCOVERIES_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.detector = BountyProgramDetector()

    def scan_repository(self, owner: str, name: str) -> CrawlResult:
        """Scan a repository for bounty program evidence."""
        logger.info(f"Scanning {owner}/{name}")

        # Fetch README
        readme_content = self._fetch_readme(owner, name)
        description = self._fetch_description(owner, name)

        if not readme_content:
            logger.debug(f"  No README found")
            return CrawlResult(
                repo_owner=owner,
                repo_name=name,
                repo_url=f"https://github.com/{owner}/{name}",
                state=AuthorizationState.UNCONFIRMED,
            )

        # Classify
        result = self.detector.classify_authorization(owner, name, readme_content, description)
        return result

    def _fetch_readme(self, owner: str, name: str) -> str:
        """Fetch README content from GitHub."""
        try:
            url = f"https://api.github.com/repos/{owner}/{name}/readme"
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/vnd.github.v3.raw"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            logger.debug(f"  Could not fetch README: {e}")
            return ""

    def _fetch_description(self, owner: str, name: str) -> str:
        """Fetch repository description."""
        try:
            url = f"https://api.github.com/repos/{owner}/{name}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("description", "")
        except Exception:
            return ""

    def save_results(self, results: list[CrawlResult], output_file: str | None = None) -> Path:
        """Save scan results to JSONL."""
        if not output_file:
            timestamp = datetime.now().isoformat()[:10]
            output_file = f"crawler_scan_{timestamp}.jsonl"

        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            for result in results:
                # Convert evidence dataclasses to dicts
                result_dict = asdict(result)
                result_dict["evidence"] = [asdict(e) for e in result.evidence]
                f.write(json.dumps(result_dict) + "\n")

        logger.info(f"Saved {len(results)} results to {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Strict bounty crawler: only finds authorized programs",
    )
    parser.add_argument(
        "--repo",
        nargs=2,
        metavar=("OWNER", "NAME"),
        help="Scan a specific repository",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Scan repositories from JSONL file (owner, name per line)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for results",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    crawler = StrictBountyCrawler(output_dir=args.output_dir)
    results = []

    if args.repo:
        owner, name = args.repo
        result = crawler.scan_repository(owner, name)
        results.append(result)
        print_result(result)

    elif args.file:
        with open(args.file) as f:
            for line in f:
                if not line.strip():
                    continue
                owner, name = line.strip().split("/")
                result = crawler.scan_repository(owner, name)
                results.append(result)

    output_path = crawler.save_results(results)

    # Summary
    authorized = [r for r in results if r.is_authorized()]
    print(f"\n✓ Scan complete: {len(authorized)}/{len(results)} authorized")
    print(f"  Output: {output_path}")

    if authorized:
        print(f"\nAuthorized programs:")
        for r in authorized:
            for ev in r.evidence:
                print(f"  → {r.repo_owner}/{r.repo_name}: {ev.program_name}")


def print_result(result: CrawlResult):
    """Pretty-print a scan result."""
    print(f"\n{result.repo_owner}/{result.repo_name}")
    print(f"  State: {result.state.value}")
    print(f"  Authorization: {result.authorization_confidence:.0%}")

    if result.evidence:
        print(f"  Evidence ({len(result.evidence)}):")
        for ev in result.evidence:
            print(f"    - {ev.program_name}: {ev.bounty_url}")

    if result.negative_signals:
        print(f"  Negative signals ({len(result.negative_signals)}):")
        for sig in result.negative_signals:
            print(f"    - {sig}")


if __name__ == "__main__":
    main()
