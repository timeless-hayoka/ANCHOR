"""Mythril adapter for ANCHOR.

Mythril JSON output typically contains:
- issues: list of dicts with title, description, severity, swc-id, filename, lineno
"""

from __future__ import annotations

from typing import List, Dict, Any

from .base import BaseAdapter
from ..parser import Finding


class MythrilAdapter(BaseAdapter):
    tool_name = "mythril"

    def parse(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> List[Finding]:
        findings: List[Finding] = []
        issues = data.get("issues", []) if isinstance(data, dict) else data

        for issue in issues:
            if not isinstance(issue, dict):
                continue

            title = issue.get("title", "Mythril finding")
            desc = issue.get("description", "")
            swc = issue.get("swc-id") or issue.get("swc")
            severity = issue.get("severity", "Medium")
            filename = issue.get("filename", "unknown")
            lineno = issue.get("lineno", 0)

            finding = self._create_finding(
                rule_id=swc or title,
                message=f"{title}: {desc[:200]}",
                file_path=filename,
                start_line=lineno,
                properties={
                    "severity": severity.lower(),
                    "swc": swc,
                    "source": "mythril",
                    "normalized": {
                        "category": self._map_category(title + " " + desc),
                        "swc": swc,
                    },
                },
            )
            findings.append(finding)

        return findings

    def _map_category(self, text: str) -> str:
        text = text.lower()
        if "reentrancy" in text:
            return "Reentrancy"
        if "access control" in text or "unauthorized" in text:
            return "Access Control"
        if "integer" in text or "overflow" in text:
            return "Arithmetic"
        if "selfdestruct" in text:
            return "Access Control"
        return "General"
