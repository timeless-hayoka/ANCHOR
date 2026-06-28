"""SARIF parsing and shared Finding model for ANCHOR."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    tool: str
    rule_id: str
    level: str
    message: str
    file_path: str
    start_line: int
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    snippet: str | None = None
    related_locations: list[dict[str, Any]] = field(default_factory=list)
    code_flows: list[list[dict[str, Any]]] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    raw_result: dict[str, Any] = field(default_factory=dict)
    dedup_key: str = ""
    normalized: dict[str, Any] = field(default_factory=dict)


def is_sarif_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    version = str(payload.get("version", ""))
    if not version.startswith("2."):
        return False
    runs = payload.get("runs")
    return isinstance(runs, list) and bool(runs)


def _normalize_uri(uri: str) -> str:
    value = str(uri or "").strip()
    if value.startswith("file://"):
        return value.removeprefix("file://")
    return value


def _rule_index(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = run.get("tool", {}).get("driver", {}).get("rules") or []
    index: dict[str, dict[str, Any]] = {}
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and rule.get("id"):
                index[str(rule["id"])] = rule
    return index


def _extract_code_flows(result: dict[str, Any]) -> list[list[dict[str, Any]]]:
    flows: list[list[dict[str, Any]]] = []
    for code_flow in result.get("codeFlows") or []:
        if not isinstance(code_flow, dict):
            continue
        for thread_flow in code_flow.get("threadFlows") or []:
            if not isinstance(thread_flow, dict):
                continue
            locations: list[dict[str, Any]] = []
            for loc in thread_flow.get("locations") or []:
                if not isinstance(loc, dict):
                    continue
                physical = loc.get("location", {}).get("physicalLocation", {})
                region = physical.get("region", {})
                locations.append(
                    {
                        "file": _normalize_uri(physical.get("artifactLocation", {}).get("uri", "")),
                        "line": region.get("startLine"),
                        "message": loc.get("location", {}).get("message", {}).get("text", ""),
                    }
                )
            if locations:
                flows.append(locations)
    return flows


def parse_sarif_payload(
    payload: dict[str, Any],
    *,
    tool_name: str = "unknown",
) -> list[Finding]:
    if not is_sarif_payload(payload):
        return []

    findings: list[Finding] = []
    for run in payload.get("runs") or []:
        if not isinstance(run, dict):
            continue
        driver = run.get("tool", {}).get("driver", {})
        tool = str(driver.get("name") or tool_name or "unknown")
        rules = _rule_index(run)

        for result in run.get("results") or []:
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId") or "unknown")
            rule_meta = rules.get(rule_id, {})
            rule_props = rule_meta.get("properties") if isinstance(rule_meta, dict) else {}
            result_props = result.get("properties") if isinstance(result.get("properties"), dict) else {}
            merged_props = {**(rule_props or {}), **(result_props or {})}

            locations = result.get("locations") or [{}]
            primary = locations[0] if locations else {}
            physical = primary.get("physicalLocation", {}) if isinstance(primary, dict) else {}
            artifact = physical.get("artifactLocation", {}) if isinstance(physical, dict) else {}
            region = physical.get("region", {}) if isinstance(physical, dict) else {}

            message_obj = result.get("message") or {}
            message = message_obj.get("text") if isinstance(message_obj, dict) else str(message_obj)
            snippet_obj = region.get("snippet") if isinstance(region, dict) else None
            snippet = snippet_obj.get("text") if isinstance(snippet_obj, dict) else None

            findings.append(
                Finding(
                    tool=tool,
                    rule_id=rule_id,
                    level=str(result.get("level") or "note"),
                    message=str(message or rule_id),
                    file_path=_normalize_uri(artifact.get("uri", "")),
                    start_line=int(region.get("startLine") or 0),
                    start_column=region.get("startColumn"),
                    end_line=region.get("endLine"),
                    end_column=region.get("endColumn"),
                    snippet=snippet,
                    related_locations=[
                        loc for loc in (result.get("relatedLocations") or []) if isinstance(loc, dict)
                    ],
                    code_flows=_extract_code_flows(result),
                    properties=merged_props,
                    raw_result=result,
                )
            )
    return findings


def parse_sarif(source: Path | dict[str, Any], *, tool_name: str = "unknown") -> list[Finding]:
    if isinstance(source, dict):
        return parse_sarif_payload(source, tool_name=tool_name)
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    return parse_sarif_payload(payload, tool_name=tool_name)
