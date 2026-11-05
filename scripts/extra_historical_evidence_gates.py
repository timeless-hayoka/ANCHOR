"""Fail-closed gates for historical Extra Finance source and liquidation claims.

Offline evidence validation only. This does not establish source equivalence.
"""
from __future__ import annotations

import re

HEX_HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
HEX_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


class EvidenceGateError(ValueError):
    """Required provenance is absent or contradictory."""


def require_source_equivalence(*, observed_runtime_hash: str,
                               compiled_runtime_hash: str,
                               compiler_version: str,
                               compiler_settings: dict,
                               linked_libraries: dict,
                               immutable_references: dict,
                               constructor_immutables_verified: bool) -> None:
    """Require an exact compiled/deployed match and explicit build provenance.

    Hash comparison must be over the final linked, immutable-substituted
    deployed runtime; no ABI or selector equivalence is accepted.
    """
    if not all(isinstance(h, str) and HEX_HASH.fullmatch(h)
               for h in (observed_runtime_hash, compiled_runtime_hash)):
        raise EvidenceGateError("missing or invalid 32-byte runtime hash")
    if observed_runtime_hash.lower() != compiled_runtime_hash.lower():
        raise EvidenceGateError("compiled/deployed runtime bytecode mismatch")
    if not isinstance(compiler_version, str) or not compiler_version.strip():
        raise EvidenceGateError("compiler version unverified")
    if not isinstance(compiler_settings, dict) or not compiler_settings:
        raise EvidenceGateError("compiler settings unverified")
    if not isinstance(linked_libraries, dict) or not isinstance(immutable_references, dict):
        raise EvidenceGateError("library/immutable provenance missing")
    if not constructor_immutables_verified:
        raise EvidenceGateError("constructor immutables not verified")
    for address in linked_libraries.values():
        if not isinstance(address, str) or not HEX_ADDRESS.fullmatch(address):
            raise EvidenceGateError("linked library address missing or invalid")


def require_liquidation_replay(*, evidence: dict, trace: dict,
                               registry_at_execution: dict,
                               observed_registry: dict,
                               source_matched: bool,
                               authentic_eligibility_proven: bool) -> None:
    """Reject promotion to liquidation replay without historical proof."""
    provenance = evidence.get("provenance", {})
    if provenance.get("chain_id") != 10 or provenance.get("read_only") is not True:
        raise EvidenceGateError("wrong chain or non-read-only evidence")
    if provenance.get("broadcast") is not False or provenance.get("storage_overrides") is not False:
        raise EvidenceGateError("broadcast or storage overrides not excluded")
    if trace.get("status") != "AVAILABLE":
        raise EvidenceGateError("historical execution trace unavailable")
    summary = trace.get("summary")
    if not isinstance(summary, dict) or summary.get("truncated") is not False:
        raise EvidenceGateError("complete execution call tree not established")
    nodes = summary.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise EvidenceGateError("execution trace has no frames")
    if not isinstance(registry_at_execution, dict) or not registry_at_execution:
        raise EvidenceGateError("historical registry snapshot missing")
    if observed_registry != registry_at_execution:
        raise EvidenceGateError("registry differs from historical execution block")
    if not source_matched:
        raise EvidenceGateError("source-to-bytecode equivalence unproven")
    if not authentic_eligibility_proven:
        raise EvidenceGateError("authentic liquidation eligibility unproven")
