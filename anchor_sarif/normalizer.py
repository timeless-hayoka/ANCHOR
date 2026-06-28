"""Map tool-specific rule IDs to a shared taxonomy (CWE, SWC, category)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .parser import Finding

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_MAPPING_FILE = _DATA_DIR / "rule_mappings.json"

_CWE_CATEGORY = {
    "CWE-89": "SQL Injection",
    "CWE-78": "Command Injection",
    "CWE-94": "Code Injection",
    "CWE-79": "Cross-Site Scripting",
    "CWE-22": "Path Traversal",
    "CWE-502": "Insecure Deserialization",
    "CWE-362": "Reentrancy",
    "CWE-284": "Access Control",
}


@dataclass
class NormalizedRule:
    original_rule_id: str
    tool: str
    cwe: str | None = None
    swc: str | None = None
    owasp: str | None = None
    category: str = "Uncategorized"
    severity_hint: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0


class RuleNormalizer:
    def __init__(self, mapping_file: Path | None = None) -> None:
        path = mapping_file or _DEFAULT_MAPPING_FILE
        self.mappings: dict[str, dict[str, Any]] = {}
        self.rule_id_fallbacks: dict[str, dict[str, Any]] = {}
        self.mapping_version = "unknown"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.mapping_version = str(payload.get("version", "1.0"))
            self.mappings = dict(payload.get("mappings") or {})
            self.rule_id_fallbacks = dict(payload.get("rule_id_fallbacks") or {})

    def normalize(self, finding: Finding) -> NormalizedRule:
        adapter_norm = (finding.properties or {}).get("normalized")
        if isinstance(adapter_norm, dict) and adapter_norm.get("category"):
            return NormalizedRule(
                original_rule_id=finding.rule_id,
                tool=finding.tool.lower().strip() or "unknown",
                cwe=adapter_norm.get("cwe"),
                swc=adapter_norm.get("swc") or finding.properties.get("swc"),
                owasp=adapter_norm.get("owasp"),
                category=str(adapter_norm.get("category")),
                tags=[str(tag) for tag in adapter_norm.get("tags", []) if tag],
                confidence=0.9,
            )

        rule_id = finding.rule_id
        tool = finding.tool.lower().strip() or "unknown"

        keyed = f"{tool}:{rule_id}"
        if keyed in self.mappings:
            return self._from_mapping(rule_id, tool, self.mappings[keyed], confidence=0.95)

        if rule_id in self.rule_id_fallbacks:
            return self._from_mapping(rule_id, tool, self.rule_id_fallbacks[rule_id], confidence=0.85)

        props = finding.properties or finding.raw_result.get("properties") or {}
        swc = props.get("swc") or props.get("swc_id") or props.get("SWC")
        cwe = props.get("cwe") or props.get("CWE")
        if swc:
            swc_text = str(swc).upper()
            if not swc_text.startswith("SWC-"):
                swc_text = f"SWC-{swc_text}"
            return NormalizedRule(
                original_rule_id=rule_id,
                tool=tool,
                swc=swc_text,
                cwe=cwe,
                category=self._category_from_swc(swc_text),
                tags=[str(tag) for tag in props.get("tags", []) if tag],
                confidence=0.9,
            )
        if cwe:
            cwe_text = str(cwe).upper()
            if not cwe_text.startswith("CWE-"):
                cwe_text = f"CWE-{cwe_text}"
            return NormalizedRule(
                original_rule_id=rule_id,
                tool=tool,
                cwe=cwe_text,
                owasp=props.get("owasp") or props.get("OWASP"),
                category=self._category_from_cwe(cwe_text),
                tags=[str(tag) for tag in props.get("tags", []) if tag],
                confidence=0.9,
            )

        category = self._heuristic_category(finding.message, rule_id)
        return NormalizedRule(
            original_rule_id=rule_id,
            tool=tool,
            category=category,
            confidence=0.6,
        )

    def _from_mapping(
        self,
        rule_id: str,
        tool: str,
        data: dict[str, Any],
        *,
        confidence: float,
    ) -> NormalizedRule:
        cwe = data.get("cwe")
        swc = data.get("swc")
        category = data.get("category")
        if not category:
            category = self._category_from_swc(swc) if swc else self._category_from_cwe(cwe)
        return NormalizedRule(
            original_rule_id=rule_id,
            tool=tool,
            cwe=str(cwe) if cwe else None,
            swc=str(swc) if swc else None,
            owasp=data.get("owasp"),
            category=str(category or "Uncategorized"),
            severity_hint=data.get("severity_hint"),
            tags=[str(tag) for tag in data.get("tags", []) if tag],
            confidence=confidence,
        )

    def _category_from_cwe(self, cwe: str | None) -> str:
        if not cwe:
            return "Uncategorized"
        return _CWE_CATEGORY.get(str(cwe).upper(), "Uncategorized")

    def _category_from_swc(self, swc: str | None) -> str:
        if not swc:
            return "Uncategorized"
        swc_upper = str(swc).upper()
        if "107" in swc_upper:
            return "Reentrancy"
        if any(code in swc_upper for code in ("105", "106", "115", "118")):
            return "Access Control"
        if any(code in swc_upper for code in ("101", "102", "103", "104")):
            return "Arithmetic"
        return "General"

    def _heuristic_category(self, message: str, rule_id: str) -> str:
        blob = f"{message} {rule_id}".lower()
        if "reentrancy" in blob or "re-entr" in blob:
            return "Reentrancy"
        if any(kw in blob for kw in ("access control", "unauthorized", "onlyowner", "selfdestruct")):
            return "Access Control"
        if any(kw in blob for kw in ("overflow", "underflow", "integer")):
            return "Arithmetic"
        if any(kw in blob for kw in ("sql", "query", "database", "sqli")):
            return "SQL Injection"
        if any(kw in blob for kw in ("eval", "exec", "system(", "subprocess", "shell")):
            return "Command/Code Injection"
        if "xss" in blob or "innerhtml" in blob or "cross-site" in blob:
            return "Cross-Site Scripting"
        if re.search(r"path.?traversal|\.\./", blob):
            return "Path Traversal"
        if "invariant" in blob:
            return "Invariant Violation"
        return "Uncategorized"
