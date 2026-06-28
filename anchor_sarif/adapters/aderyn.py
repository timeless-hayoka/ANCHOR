"""Aderyn adapter for ANCHOR.

Aderyn outputs JSON with issues containing:
- title, description, severity, swc_id, location (file, line)
"""

from __future__ import annotations

from typing import List, Dict, Any

from .base import BaseAdapter
from ..parser import Finding


class AderynAdapter(BaseAdapter):
    tool_name = "aderyn"

    def parse(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> List[Finding]:
        findings: List[Finding] = []

        issues = data.get("issues", []) if isinstance(data, dict) else data

        for issue in issues:
            if not isinstance(issue, dict):
                continue

            swc = issue.get("swc_id") or issue.get("swc")
            title = issue.get("title", issue.get("description", "Unknown issue"))
            severity = issue.get("severity", "medium")
            loc = issue.get("location", {})
            file_path = loc.get("file_path", loc.get("path", "unknown"))
            line = loc.get("line", loc.get("start_line", 0))

            finding = self._create_finding(
                rule_id=swc or title,
                message=title,
                file_path=file_path,
                start_line=line,
                properties={
                    "severity": severity,
                    "swc": swc,
                    "source": "aderyn",
                    "normalized": {"category": self._map_to_category(swc or title), "swc": swc},
                },
            )
            findings.append(finding)

        return findings

    def _map_to_category(self, text: str) -> str:
        text = text.lower()
        if "reentrancy" in text:
            return "Reentrancy"
        if "access" in text or "owner" in text:
            return "Access Control"
        if "overflow" in text or "underflow" in text:
            return "Arithmetic"
        return "General"
