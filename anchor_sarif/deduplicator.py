"""Deduplicate findings across tools and runs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .parser import Finding


@dataclass
class DeduplicationResult:
    unique_findings: list[Finding] = field(default_factory=list)
    duplicate_count: int = 0
    merged_keys: dict[str, list[str]] = field(default_factory=dict)


class SARIFDeduplicator:
    def __init__(self, *, line_tolerance: int = 3) -> None:
        self.line_tolerance = max(0, line_tolerance)

    def location_key(self, finding: Finding) -> str:
        line_bucket = finding.start_line // max(1, self.line_tolerance + 1)
        return f"{finding.tool}|{finding.rule_id}|{finding.file_path}|{line_bucket}"

    def normalized_key(self, finding: Finding) -> str:
        norm = finding.normalized or {}
        category = norm.get("category") or "Uncategorized"
        cwe = norm.get("cwe") or ""
        swc = norm.get("swc") or ""
        line_bucket = finding.start_line // max(1, self.line_tolerance + 1)
        return f"{category}|{cwe}|{swc}|{finding.file_path}|{line_bucket}"

    def content_hash_key(self, finding: Finding) -> str:
        content = f"{finding.rule_id}|{finding.message[:200]}|{finding.snippet or ''}"
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:24]

    def key_strategy(self, finding: Finding, *, strategy: str = "normalized") -> str:
        if strategy == "location":
            return self.location_key(finding)
        if strategy == "content_hash":
            return self.content_hash_key(finding)
        return self.normalized_key(finding)

    def deduplicate_cross_tool(
        self,
        findings_by_tool: dict[str, list[Finding]],
        *,
        strategy: str = "normalized",
    ) -> DeduplicationResult:
        merged: list[Finding] = []
        for findings in findings_by_tool.values():
            merged.extend(findings)
        return self.deduplicate(merged, strategy=strategy)

    def deduplicate(
        self,
        findings: list[Finding],
        *,
        strategy: str = "location",
    ) -> DeduplicationResult:
        if not findings:
            return DeduplicationResult()

        key_fn = self.location_key
        if strategy == "normalized":
            key_fn = self.normalized_key
        elif strategy == "content_hash":
            key_fn = self.content_hash_key

        seen: dict[str, Finding] = {}
        merged: dict[str, list[str]] = {}
        duplicates = 0

        for finding in findings:
            key = key_fn(finding)
            finding.dedup_key = key
            if key in seen:
                duplicates += 1
                merged.setdefault(key, [seen[key].tool]).append(finding.tool)
                continue
            seen[key] = finding
            merged[key] = [finding.tool]

        return DeduplicationResult(
            unique_findings=list(seen.values()),
            duplicate_count=duplicates,
            merged_keys=merged,
        )
