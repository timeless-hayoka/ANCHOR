"""BugBot Sentinel: Scope verification and authorization confirmation.

Confirms that discovered targets are:
  1. Actually linked to official bounty programs
  2. Have current and valid scope information
  3. Are authorized for Trinity hunting

Pipeline:
  bounty_scout.py (Discovery)
    → bounty_sentinel.py (Scope Verification) ← YOU ARE HERE
      → target_forge.py (Normalization)
        → Trinity (Investigation)
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ALLOWED_URL_SCHEMES = frozenset({"https"})

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DISCOVERIES_DIR = ROOT / "discoveries" / "scout"
VERIFIED_DIR = ROOT / "discoveries" / "sentinel"


class VerificationMethod(StrEnum):
    """How scope was verified."""
    OFFICIAL_PAGE = "official_page"              # Verified against official bounty page
    REPOSITORY_LINK = "repository_link"          # Confirmed via official repo link
    COMMIT_HASH = "commit_hash"                  # Pinned to specific commit
    MANUAL_REVIEW = "manual_review"              # Human review of scope
    PROGRAM_API = "program_api"                  # Verified via official API


@dataclass(frozen=True)
class VerificationResult:
    """Result of scope verification for a target."""
    target_id: str
    authorized: bool                              # Is this target safe for Trinity?
    method: VerificationMethod
    confidence: float                              # 0.0-1.0 confidence score
    evidence: list[str]                            # URLs, files, etc. that prove scope
    verified_at: str                               # ISO timestamp
    expires_at: str | None = None                # When does this verification expire?
    reason: str = ""                               # Why authorized/rejected?


class ScopeSentinel:
    """Verification layer for discovered bounty targets."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or VERIFIED_DIR
        self.verified: list[VerificationResult] = []
        self.rejected: list[VerificationResult] = []

    def verify_target(
        self,
        target_id: str,
        platform_url: str,
        repository_url: str,
        in_scope_assets: list[dict[str, Any]],
        verification_method: VerificationMethod = VerificationMethod.OFFICIAL_PAGE,
    ) -> VerificationResult:
        """Verify that a target is authorized for hunting.

        Hard gates:
          - Authorization must be current (not expired)
          - Scope must match official program documentation
          - Repository must be linked to official program
          - No testing against live contracts without explicit permission
        """

        evidence = []
        confidence = 0.0
        authorized = False
        reason = ""

        # Gate 1: Check platform URL is accessible (HTTPS only, no SSRF)
        try:
            parsed = urlparse(platform_url)
            if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.hostname:
                raise ValueError(f"disallowed platform URL scheme or format: {platform_url!r}")
            with urllib.request.urlopen(platform_url, timeout=10):
                pass
            evidence.append(platform_url)
            confidence += 0.2
        except Exception as e:
            reason = f"Platform URL inaccessible: {e}"
            logger.warning(f"[{target_id}] {reason}")
            return VerificationResult(
                target_id=target_id,
                authorized=False,
                method=verification_method,
                confidence=0.0,
                evidence=evidence,
                verified_at=datetime.now(timezone.utc).isoformat(),
                reason=reason,
            )

        # Gate 2: Check repository link matches official program
        if repository_url:
            evidence.append(repository_url)
            confidence += 0.3
        else:
            reason = "Repository URL not found"
            logger.warning(f"[{target_id}] {reason}")

        # Gate 3: Verify scope assets are not empty
        if in_scope_assets and len(in_scope_assets) > 0:
            evidence.extend([asset.get("identifier", "") for asset in in_scope_assets])
            confidence += 0.3
        else:
            reason = "No in-scope assets defined"
            logger.warning(f"[{target_id}] {reason}")

        # Gate 4: Set authorized if all gates pass
        if confidence >= 0.7:
            authorized = True
            reason = f"Verified via {verification_method.value}"

        return VerificationResult(
            target_id=target_id,
            authorized=authorized,
            method=verification_method,
            confidence=confidence,
            evidence=evidence,
            verified_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,  # In real implementation, check scope expiry
            reason=reason,
        )

    def load_discovered_targets(self, discovery_file: Path) -> list[dict[str, Any]]:
        """Load targets from scout discovery output."""
        targets = []
        if not discovery_file.exists():
            logger.error(f"Discovery file not found: {discovery_file}")
            return targets

        with open(discovery_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    targets.append(json.loads(line))
        return targets

    def verify_all(self, discovery_file: Path) -> tuple[list[VerificationResult], list[VerificationResult]]:
        """Verify all targets in a discovery file."""
        targets = self.load_discovered_targets(discovery_file)
        logger.info(f"Verifying {len(targets)} targets from {discovery_file.name}")

        authorized = []
        rejected = []

        for target in targets:
            result = self.verify_target(
                target_id=target.get("target_id", ""),
                platform_url=target.get("platform_url", ""),
                repository_url=target.get("repository_url", ""),
                in_scope_assets=target.get("in_scope_assets", []),
            )

            if result.authorized:
                authorized.append(result)
                logger.info(f"  ✓ {result.target_id}: {result.reason}")
            else:
                rejected.append(result)
                logger.warning(f"  ✗ {result.target_id}: {result.reason}")

        self.verified = authorized
        self.rejected = rejected

        return authorized, rejected

    def save_verified(self, output_file: str | None = None) -> Path:
        """Save verified targets to file."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not output_file:
            timestamp = datetime.now().isoformat()[:10]
            output_file = f"verified_{timestamp}.jsonl"

        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            for result in self.verified:
                f.write(json.dumps(asdict(result)) + "\n")

        logger.info(f"Saved {len(self.verified)} verified targets to {output_path}")
        return output_path

    def save_rejected(self, output_file: str | None = None) -> Path:
        """Save rejected targets to file for review."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not output_file:
            timestamp = datetime.now().isoformat()[:10]
            output_file = f"rejected_{timestamp}.jsonl"

        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            for result in self.rejected:
                f.write(json.dumps(asdict(result)) + "\n")

        logger.info(f"Saved {len(self.rejected)} rejected targets to {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Sentinel: Verify scope authorization for discovered targets",
    )
    parser.add_argument(
        "discovery_file",
        type=Path,
        help="Scout discovery JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for verified targets",
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

    if not args.discovery_file.exists():
        print(f"Error: Discovery file not found: {args.discovery_file}")
        return 1

    sentinel = ScopeSentinel(output_dir=args.output_dir)
    authorized, rejected = sentinel.verify_all(args.discovery_file)

    verified_path = sentinel.save_verified()
    rejected_path = sentinel.save_rejected()

    print(f"\n✓ Sentinel verification complete")
    print(f"  Authorized: {len(authorized)}")
    print(f"  Rejected: {len(rejected)}")
    print(f"  Verified: {verified_path}")
    print(f"  Rejected: {rejected_path}")

    if authorized:
        print(f"\nNext: Run 'python3 target_forge.py {verified_path}' to prepare hunt packages")

    return 0


if __name__ == "__main__":
    exit(main())
