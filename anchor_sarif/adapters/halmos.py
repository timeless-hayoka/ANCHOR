"""Halmos adapter for ANCHOR.

Halmos (symbolic execution on Foundry) typically outputs:
- counterexamples or failed invariants with location info.
For simplicity, we treat failed invariants as high-confidence findings.
"""

from __future__ import annotations

from typing import List, Dict, Any

from .base import BaseAdapter
from ..parser import Finding


class HalmosAdapter(BaseAdapter):
    tool_name = "halmos"

    def parse(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> List[Finding]:
        findings: List[Finding] = []

        results = data if isinstance(data, list) else data.get("results", [])

        for item in results:
            if not isinstance(item, dict):
                continue

            name = item.get("name", item.get("invariant", "Halmos finding"))
            status = item.get("status", "")
            if status.lower() != "failed":
                continue

            filename = item.get("filename", "unknown")
            lineno = item.get("line", 0)

            finding = self._create_finding(
                rule_id=f"halmos-{name}",
                message=f"Invariant violation: {name}",
                file_path=filename,
                start_line=lineno,
                properties={
                    "severity": "high",
                    "source": "halmos",
                    "normalized": {"category": "Invariant Violation"},
                    "is_invariant": True,
                },
            )
            findings.append(finding)

        return findings
