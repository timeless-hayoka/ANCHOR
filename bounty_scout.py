"""BugBot Scout: Automated discovery of authorized bounty programs.

Discovers smart contract bounty programs from official platforms and normalizes
them into standardized target records with authorization proof.

Pipeline:
  bounty_scout.py (Discovery)
    → bounty_sentinel.py (Scope Verification)
      → target_forge.py (Normalization)
        → Trinity (Investigation)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DISCOVERIES_DIR = ROOT / "discoveries" / "scout"


class BountyPlatform(StrEnum):
    """Supported bounty discovery platforms."""
    IMMUNEFI = "immunefi"
    CODE4RENA = "code4rena"
    SHERLOCK = "sherlock"
    CANTINA = "cantina"
    HACKERONE = "hackerone"


class AuthorizationStatus(StrEnum):
    """Authorization lifecycle states for discovered targets."""
    DISCOVERED = "discovered"                  # Initial discovery, scope unknown
    SCOPE_UNVERIFIED = "scope_unverified"      # Source found, scope not confirmed
    SCOPE_VERIFIED = "scope_verified"          # Scope confirmed, ready for Trinity
    STALE = "stale"                            # Program closed or scope expired
    OUT_OF_SCOPE = "out_of_scope"              # Explicitly out of hunting scope
    REJECTED = "rejected"                      # Failed authorization checks


@dataclass(frozen=True)
class ScopeAsset:
    """An in-scope or out-of-scope asset within a bounty program."""
    asset_type: str  # "contract", "chain", "file_path", "function", etc.
    identifier: str  # contract address, chain name, file path, function sig, etc.
    label: str = ""  # human-readable label
    notes: str = ""  # additional context


@dataclass(frozen=True)
class SeverityRules:
    """Severity and payout structure for a program."""
    critical_usd_min: int = 0
    critical_usd_max: int = 0
    high_usd_min: int = 0
    high_usd_max: int = 0
    medium_usd_min: int = 0
    medium_usd_max: int = 0
    low_usd_min: int = 0
    low_usd_max: int = 0


@dataclass(frozen=True)
class DiscoveredTarget:
    """Discovered bounty program target ready for scope verification."""
    target_id: str                                      # yearn-v3, aave-governance, etc.
    program_name: str                                  # "Yearn Finance v3", "Aave Governance", etc.
    platform: BountyPlatform                           # which bounty platform
    platform_url: str                                  # link to bounty page
    program_url: str = ""                              # link to official program documentation
    repository_url: str = ""                           # GitHub repo if known

    # Authorization tracking
    authorization_status: AuthorizationStatus = AuthorizationStatus.DISCOVERED
    scope_verification_url: str = ""                   # URL used to verify scope
    verified_at: str = ""                              # ISO timestamp of verification
    verification_method: str = ""                      # how was scope confirmed? "page_scrape", "api", "manual"

    # Scope details (populated after verification)
    in_scope_assets: list[ScopeAsset] = field(default_factory=list)
    out_of_scope_assets: list[ScopeAsset] = field(default_factory=list)
    severity_rules: SeverityRules | None = None
    submission_rules: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)

    # Metadata
    languages: list[str] = field(default_factory=list)  # ["Solidity", "Rust", etc.]
    framework: str = ""                                 # "foundry", "hardhat", "truffle", etc.
    chain: str = ""                                     # "ethereum", "arbitrum", etc.
    kyc_required: bool | None = None
    payout_range: str = ""                              # e.g. "$1,000 - $100,000"

    # Staleness tracking
    last_verified_at: str = ""                          # ISO timestamp
    scope_expires_at: str | None = None                # when does this scope become invalid?

    # Evidence
    crawler_evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ScoutDiscovery:
    """Summary of a scout run."""
    platform: BountyPlatform
    discovered_count: int = 0
    errors: list[str] = field(default_factory=list)
    targets: list[DiscoveredTarget] = field(default_factory=list)
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ImmunefiBountyClient:
    """Immunefi bounty discovery client (requires network access)."""

    API_BASE = "https://immunefi.com/api"

    def __init__(self):
        self.session_headers = {
            "User-Agent": "ANCHOR-BugBot-Scout/1.0",
            "Accept": "application/json",
        }

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        """Execute Immunefi API request."""
        url = f"{self.API_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url, headers=self.session_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.warning("Immunefi API access denied (403). Check network policy.")
                return {} if "application/json" in e.headers.get("Content-Type", "") else []
            if e.code == 404:
                return {}
            raise

    def list_programs(self) -> list[dict[str, Any]]:
        """Fetch active bounty programs from Immunefi."""
        try:
            result = self._request("/programs")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Failed to fetch Immunefi programs: {e}")
            return []

    def get_program_details(self, program_id: str) -> dict[str, Any]:
        """Fetch detailed information for a specific program."""
        try:
            result = self._request(f"/programs/{program_id}")
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.error(f"Failed to fetch program {program_id}: {e}")
            return {}


class Code4RenaBountyClient:
    """Code4rena contest discovery client (requires network access)."""

    API_BASE = "https://code4rena.com/api"

    def __init__(self):
        self.session_headers = {
            "User-Agent": "ANCHOR-BugBot-Scout/1.0",
            "Accept": "application/json",
        }

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        """Execute Code4rena API request."""
        url = f"{self.API_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url, headers=self.session_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.warning("Code4rena API access denied (403). Check network policy.")
                return {} if "application/json" in e.headers.get("Content-Type", "") else []
            if e.code == 404:
                return {}
            raise

    def list_contests(self, status: str = "open") -> list[dict[str, Any]]:
        """Fetch active contests from Code4rena."""
        try:
            result = self._request("/contests", {"status": status})
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Failed to fetch Code4rena contests: {e}")
            return []

    def get_contest_details(self, contest_id: str) -> dict[str, Any]:
        """Fetch detailed information for a specific contest."""
        try:
            result = self._request(f"/contests/{contest_id}")
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.error(f"Failed to fetch contest {contest_id}: {e}")
            return {}


class BountyScouter:
    """Main scout orchestration for discovering bounty programs."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or DISCOVERIES_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.immunefi = ImmunefiBountyClient()
        self.code4rena = Code4RenaBountyClient()

    def discover_immunefi(self) -> ScoutDiscovery:
        """Discover programs from Immunefi."""
        logger.info("Discovering Immunefi programs...")
        discovery = ScoutDiscovery(platform=BountyPlatform.IMMUNEFI)

        programs = self.immunefi.list_programs()
        logger.info(f"Found {len(programs)} Immunefi programs")

        for program in programs:
            try:
                target = self._normalize_immunefi_program(program)
                if target:
                    discovery.targets.append(target)
                    discovery.discovered_count += 1
            except Exception as e:
                logger.warning(f"Failed to normalize program: {e}")
                discovery.errors.append(str(e))

        return discovery

    def discover_code4rena(self) -> ScoutDiscovery:
        """Discover contests from Code4rena."""
        logger.info("Discovering Code4rena contests...")
        discovery = ScoutDiscovery(platform=BountyPlatform.CODE4RENA)

        contests = self.code4rena.list_contests(status="open")
        logger.info(f"Found {len(contests)} Code4rena contests")

        for contest in contests:
            try:
                target = self._normalize_code4rena_contest(contest)
                if target:
                    discovery.targets.append(target)
                    discovery.discovered_count += 1
            except Exception as e:
                logger.warning(f"Failed to normalize contest: {e}")
                discovery.errors.append(str(e))

        return discovery

    def _normalize_immunefi_program(self, program: dict[str, Any]) -> DiscoveredTarget | None:
        """Convert Immunefi program to DiscoveredTarget."""
        program_id = program.get("id", "")
        program_name = program.get("name", "")

        if not program_id or not program_name:
            return None

        in_scope_assets = []
        for asset in program.get("inScopeAssets", []):
            in_scope_assets.append(
                ScopeAsset(
                    asset_type=asset.get("type", "contract"),
                    identifier=asset.get("address", asset.get("id", "")),
                    label=asset.get("label", ""),
                )
            )

        return DiscoveredTarget(
            target_id=program_id,
            program_name=program_name,
            platform=BountyPlatform.IMMUNEFI,
            platform_url=f"https://immunefi.com/bug-bounty/{program_id}",
            program_url=program.get("website", ""),
            repository_url=program.get("repository", ""),
            authorization_status=AuthorizationStatus.SCOPE_UNVERIFIED,
            in_scope_assets=in_scope_assets,
            languages=program.get("languages", []),
            framework=program.get("framework", ""),
            chain=program.get("chain", ""),
            kyc_required=program.get("kyc_required"),
            payout_range=program.get("payout_range", ""),
            last_verified_at=datetime.now(timezone.utc).isoformat(),
            crawler_evidence=[{"source": "immunefi_api", "timestamp": datetime.now(timezone.utc).isoformat()}],
        )

    def _normalize_code4rena_contest(self, contest: dict[str, Any]) -> DiscoveredTarget | None:
        """Convert Code4rena contest to DiscoveredTarget."""
        contest_id = contest.get("id", "")
        contest_name = contest.get("name", "")

        if not contest_id or not contest_name:
            return None

        in_scope_files = []
        for file in contest.get("in_scope_files", []):
            in_scope_files.append(
                ScopeAsset(
                    asset_type="file_path",
                    identifier=file.get("path", ""),
                    label=file.get("name", ""),
                )
            )

        return DiscoveredTarget(
            target_id=contest_id,
            program_name=contest_name,
            platform=BountyPlatform.CODE4RENA,
            platform_url=f"https://code4rena.com/contests/{contest_id}",
            program_url=contest.get("documentation_url", ""),
            repository_url=contest.get("repository", ""),
            authorization_status=AuthorizationStatus.SCOPE_UNVERIFIED,
            in_scope_assets=in_scope_files,
            languages=["Solidity"],
            framework=contest.get("framework", "foundry"),
            chain=contest.get("chain", "ethereum"),
            kyc_required=contest.get("kyc_required"),
            payout_range=contest.get("prize_pool", ""),
            last_verified_at=datetime.now(timezone.utc).isoformat(),
            crawler_evidence=[{"source": "code4rena_api", "timestamp": datetime.now(timezone.utc).isoformat()}],
        )

    def save_discovery(self, discovery: ScoutDiscovery, filename: str | None = None) -> Path:
        """Save discovery results to JSONL file."""
        if not filename:
            timestamp = datetime.now().isoformat()[:10]
            filename = f"scout_{discovery.platform}_{timestamp}.jsonl"

        output_path = self.output_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            for target in discovery.targets:
                f.write(json.dumps(asdict(target)) + "\n")

        logger.info(f"Saved {len(discovery.targets)} targets to {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Scout: Discover authorized bounty programs",
    )
    parser.add_argument(
        "--platform",
        choices=[p.value for p in BountyPlatform],
        default="immunefi",
        help="Bounty platform to discover from",
    )
    parser.add_argument(
        "--all-platforms",
        action="store_true",
        help="Discover from all platforms",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for discovered targets",
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

    scout = BountyScouter(output_dir=args.output_dir)

    all_discoveries = []

    if args.all_platforms:
        for platform in BountyPlatform:
            if platform == BountyPlatform.IMMUNEFI:
                discovery = scout.discover_immunefi()
                output_path = scout.save_discovery(discovery)
                all_discoveries.append((platform, output_path, discovery))
            elif platform == BountyPlatform.CODE4RENA:
                discovery = scout.discover_code4rena()
                output_path = scout.save_discovery(discovery)
                all_discoveries.append((platform, output_path, discovery))
            else:
                logger.error(f"Platform {platform.value} not yet implemented")
    else:
        platform = BountyPlatform(args.platform)
        if platform == BountyPlatform.IMMUNEFI:
            discovery = scout.discover_immunefi()
            output_path = scout.save_discovery(discovery)
            all_discoveries.append((platform, output_path, discovery))
        elif platform == BountyPlatform.CODE4RENA:
            discovery = scout.discover_code4rena()
            output_path = scout.save_discovery(discovery)
            all_discoveries.append((platform, output_path, discovery))
        else:
            print(f"Error: Platform '{platform.value}' is not yet implemented")
            print(f"Supported platforms: {', '.join(p.value for p in [BountyPlatform.IMMUNEFI, BountyPlatform.CODE4RENA])}")
            return 1

    # Summary
    total_discovered = sum(d[2].discovered_count for d in all_discoveries)
    print(f"\n✓ Scout run complete")
    print(f"  Total discovered: {total_discovered} targets")
    for platform, output_path, _ in all_discoveries:
        print(f"  → {output_path}")

    print(f"\nNext: Run 'python3 bounty_sentinel.py' to verify scope on discovered targets")


if __name__ == "__main__":
    main()
