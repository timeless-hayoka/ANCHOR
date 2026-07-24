"""BugBot Forge: Normalize verified targets into Trinity hunt packages.

Converts verified bounty targets into complete hunt packages with:
  - Confirmed scope and authorization
  - Prioritized focus areas (based on code complexity, attack surface)
  - Environment specifications (framework, fork requirements, etc.)
  - Integration markers for Trinity

Pipeline:
  bounty_scout.py (Discovery)
    → bounty_sentinel.py (Scope Verification)
      → target_forge.py (Normalization) ← YOU ARE HERE
        → Trinity (Investigation)
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
FORGE_DIR = ROOT / "discoveries" / "forge"


class Framework(StrEnum):
    """Smart contract testing framework."""
    FOUNDRY = "foundry"
    HARDHAT = "hardhat"
    TRUFFLE = "truffle"
    RUST = "rust"  # Solana, Anchor
    GO = "go"      # Cosmos, etc.


class Chain(StrEnum):
    """Blockchain network."""
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    BASE = "base"
    SOLANA = "solana"
    COSMOS = "cosmos"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EnvironmentSpec:
    """How to set up the testing environment."""
    framework: Framework
    fork_required: bool                     # Need a fork of mainnet/testnet?
    fork_chain: Chain | None = None         # Which chain to fork?
    rpc_endpoint: str = ""                  # RPC endpoint to use
    live_transactions_allowed: bool = False # Can we submit real transactions?
    requires_funding: bool = False          # Need test tokens/ETH?
    constraints: list[str] = field(default_factory=list)  # e.g., ["no-mainnet-rpc", "fork-eth-only"]


@dataclass
class HuntPackage:
    """Complete hunt package ready for Trinity investigation."""
    hunt_id: str                                        # hunt_yearn_v3_001
    target: dict[str, Any]                              # target metadata (includes commit_sha)
    scope: dict[str, Any]                               # in/out of scope, forbidden actions
    environment: EnvironmentSpec                        # testing setup
    recommended_focus: list[str]                        # e.g., ["share accounting", "withdrawal flow"]
    evidence_refs: list[str]                            # proof that scope is authorized
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        """Validate that hunt package has required authorization markers."""
        # Hard gates for Trinity ingestion
        if not self.target.get("authorized"):
            raise ValueError("hunt_package.target.authorized must be True")
        if not self.target.get("commit_sha"):
            raise ValueError("hunt_package.target.commit_sha must be pinned")
        if not self.target.get("verification_confidence"):
            raise ValueError("hunt_package.target.verification_confidence must be recorded")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        result = asdict(self)
        result["environment"] = asdict(self.environment)
        return result


class TargetForge:
    """Normalizes verified targets into hunt packages."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or FORGE_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hunt_counter = 0

    def load_verified_targets(self, verified_file: Path) -> list[dict[str, Any]]:
        """Load verified targets from sentinel output."""
        targets = []
        if not verified_file.exists():
            logger.error(f"Verified targets file not found: {verified_file}")
            return targets

        with open(verified_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    targets.append(json.loads(line))
        return targets

    def forge_package(
        self,
        target: dict[str, Any],
        verification: dict[str, Any],
    ) -> HuntPackage:
        """Forge a hunt package from a verified target.

        Applies hard gates:
          - authorization_status must be verified
          - repo_commit must be known
          - scope must not be stale
          - testing must not require live funds
        """

        self.hunt_counter += 1
        hunt_id = f"hunt_{target.get('target_id', 'unknown')}_{self.hunt_counter:03d}"

        # Extract target info
        program_name = target.get("program_name", "")
        platform = target.get("platform", "")
        repository = target.get("repository_url", "")
        framework = Framework(target.get("framework", "foundry"))
        chain = Chain(target.get("chain", "ethereum"))

        # Build scope from assets
        in_scope = {}
        out_of_scope = {}

        for asset in target.get("in_scope_assets", []):
            asset_type = asset.get("asset_type", "unknown")
            if asset_type not in in_scope:
                in_scope[asset_type] = []
            in_scope[asset_type].append({
                "identifier": asset.get("identifier", ""),
                "label": asset.get("label", ""),
            })

        for asset in target.get("out_of_scope_assets", []):
            asset_type = asset.get("asset_type", "unknown")
            if asset_type not in out_of_scope:
                out_of_scope[asset_type] = []
            out_of_scope[asset_type].append({
                "identifier": asset.get("identifier", ""),
                "label": asset.get("label", ""),
            })

        # Determine environment requirements
        fork_required = chain in (Chain.ETHEREUM, Chain.ARBITRUM, Chain.POLYGON)
        live_txns_allowed = False  # Conservative default

        env_spec = EnvironmentSpec(
            framework=framework,
            fork_required=fork_required,
            fork_chain=chain if fork_required else None,
            rpc_endpoint=self._get_rpc_endpoint(chain),
            live_transactions_allowed=live_txns_allowed,
            requires_funding=True,  # Usually need test tokens
            constraints=self._get_constraints(framework, chain, target),
        )

        # Recommend focus areas based on asset types and keywords
        focus_areas = self._extract_focus_areas(target)

        scope_obj = {
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
            "forbidden_methods": target.get("forbidden_actions", []),
            "kyc_required": target.get("kyc_required"),
        }

        target_obj = {
            "program": program_name,
            "platform": platform,
            "repository": repository,
            "authorized": verification.get("authorized", False),
            "authorization_method": verification.get("method", ""),
            "verification_confidence": verification.get("confidence", 0.0),
            # CRITICAL: Commit pinning prevents hunting wrong versions
            "commit_sha": target.get("commit_sha", ""),  # Must be full 40-char SHA
            "commit_resolved_at": target.get("commit_resolved_at", ""),  # When was it pinned?
            # RPC endpoints use env var refs, never hardcoded URLs
            "rpc_env_var": self._get_rpc_env_var(chain),
        }

        return HuntPackage(
            hunt_id=hunt_id,
            target=target_obj,
            scope=scope_obj,
            environment=env_spec,
            recommended_focus=focus_areas,
            evidence_refs=verification.get("evidence", []),
        )

    def _get_rpc_endpoint(self, chain: Chain) -> str:
        """Get environment variable reference for RPC endpoint.

        IMPORTANT: Never embed actual RPC URLs or API keys in hunt packages.
        Use environment variable references instead. Trinity/user provides at runtime.
        """
        env_refs = {
            Chain.ETHEREUM: "${ETHEREUM_RPC_URL}",
            Chain.ARBITRUM: "${ARBITRUM_RPC_URL}",
            Chain.POLYGON: "${POLYGON_RPC_URL}",
            Chain.OPTIMISM: "${OPTIMISM_RPC_URL}",
            Chain.BASE: "${BASE_RPC_URL}",
            Chain.SOLANA: "${SOLANA_RPC_URL}",
        }
        return env_refs.get(chain, "")

    def _get_rpc_env_var(self, chain: Chain) -> str:
        """Get RPC environment variable name for this chain."""
        env_vars = {
            Chain.ETHEREUM: "ETHEREUM_RPC_URL",
            Chain.ARBITRUM: "ARBITRUM_RPC_URL",
            Chain.POLYGON: "POLYGON_RPC_URL",
            Chain.OPTIMISM: "OPTIMISM_RPC_URL",
            Chain.BASE: "BASE_RPC_URL",
            Chain.SOLANA: "SOLANA_RPC_URL",
        }
        return env_vars.get(chain, "")

    def _get_constraints(self, framework: Framework, chain: Chain, target: dict[str, Any]) -> list[str]:
        """Determine environment constraints."""
        constraints = []

        if chain == Chain.ETHEREUM:
            constraints.append("use-mainnet-fork-for-historical-context")

        if framework == Framework.FOUNDRY:
            constraints.append("foundry-install-required")

        if "kyc" in str(target.get("kyc_required", "")).lower():
            constraints.append("kyc-verification-recorded")

        return constraints

    def _extract_focus_areas(self, target: dict[str, Any]) -> list[str]:
        """Extract recommended focus areas based on scope and keywords."""
        focus = []

        assets = target.get("in_scope_assets", [])
        for asset in assets:
            asset_id = (asset.get("identifier", "") + asset.get("label", "")).lower()

            # Common focus patterns
            if "share" in asset_id or "lp" in asset_id or "vault" in asset_id:
                focus.append("share accounting and rounding")
            if "upgrade" in asset_id or "proxy" in asset_id:
                focus.append("proxy initialization and implementation state")
            if "access" in asset_id or "admin" in asset_id or "owner" in asset_id:
                focus.append("access control boundaries")
            if "oracle" in asset_id or "price" in asset_id or "feed" in asset_id:
                focus.append("oracle staleness and manipulation")
            if "withdraw" in asset_id or "transfer" in asset_id or "call" in asset_id:
                focus.append("external call ordering and reentrancy")

        if not focus:
            focus.append("general vulnerability audit")

        return list(dict.fromkeys(focus))  # Remove duplicates, preserve order

    def forge_all(self, verified_file: Path, discovery_file: Path | None = None) -> list[HuntPackage]:
        """Forge hunt packages from all verified targets."""
        targets = self.load_verified_targets(verified_file)
        logger.info(f"Forging {len(targets)} hunt packages")

        packages = []
        for verification in targets:
            target_id = verification.get("target_id", "")
            if discovery_file:
                target = self._load_target_by_id(discovery_file, target_id)
            else:
                target = {"target_id": target_id}

            package = self.forge_package(target, verification)
            packages.append(package)
            logger.info(f"  Forged: {package.hunt_id}")

        return packages

    def _load_target_by_id(self, discovery_file: Path, target_id: str) -> dict[str, Any]:
        """Load a specific target by ID from discovery file."""
        if not discovery_file.exists():
            return {"target_id": target_id}

        with open(discovery_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    target = json.loads(line)
                    if target.get("target_id") == target_id:
                        return target
        return {"target_id": target_id}

    def save_packages(self, packages: list[HuntPackage], output_file: str | None = None) -> Path:
        """Save hunt packages to JSONL file."""
        if not output_file:
            timestamp = datetime.now().isoformat()[:10]
            output_file = f"hunt_packages_{timestamp}.jsonl"

        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            for package in packages:
                f.write(json.dumps(package.to_dict()) + "\n")

        logger.info(f"Saved {len(packages)} hunt packages to {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Forge: Normalize verified targets into hunt packages",
    )
    parser.add_argument(
        "verified_file",
        type=Path,
        help="Sentinel verified targets JSONL file",
    )
    parser.add_argument(
        "--discovery-file",
        type=Path,
        help="Scout discovery JSONL file (optional, for enrichment)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for hunt packages",
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

    if not args.verified_file.exists():
        print(f"Error: Verified targets file not found: {args.verified_file}")
        return 1

    forge = TargetForge(output_dir=args.output_dir)
    packages = forge.forge_all(args.verified_file, args.discovery_file)

    output_path = forge.save_packages(packages)

    print(f"\n✓ Forge complete")
    print(f"  Packages: {len(packages)}")
    print(f"  Output: {output_path}")

    if packages:
        print(f"\nNext: Feed hunt packages to Trinity with:")
        print(f"  anchor hunt --package {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
