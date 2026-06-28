"""Full End-to-End SARIF + Multi-tool Ensemble Pipeline for ANCHOR.

Workflow stages (single pipeline, no separate validator models):
  ingest → normalize → deduplicate → signal_filter → cluster → enrich → persist

ANCHOR is the only reasoning layer: optional llm_summarizer is ANCHOR's voice for
cluster summaries, not a second triage model.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any

from .parser import parse_sarif, Finding, is_sarif_payload
from .normalizer import RuleNormalizer, NormalizedRule
from .deduplicator import SARIFDeduplicator
from .semantic_clusterer import SemanticClusterer, ClusterResult
from .fp_heuristics import assess_signal_noise, should_drop_signal
from .future_state import rewrite_finding
from .economic_context import assess_economic_context
from .validator_bridge import validate_candidate
from .adapters.aderyn import AderynAdapter
from .adapters.mythril import MythrilAdapter
from .adapters.halmos import HalmosAdapter


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PipelineRunStats:
    ingested: int = 0
    after_dedup: int = 0
    signal_discarded: int = 0
    signal_promoted: int = 0
    signal_review: int = 0
    clustered: int = 0
    persisted: int = 0

    @property
    def signal_discard_rate(self) -> float:
        if not self.after_dedup:
            return 0.0
        return round(self.signal_discarded / self.after_dedup, 4)


@dataclass
class EnrichedFinding:
    finding: Finding
    normalized: NormalizedRule
    source_context: Optional[str] = None
    dedup_key: str = ""
    cluster_id: Optional[int] = None
    cluster_summary: str = ""
    processed_at: str = field(default_factory=utcnow_iso)


class SARIFProcessingPipeline:
    def __init__(
        self,
        db_path: Path = Path("anchor_sarif_findings.db"),
        enable_semantic_clustering: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
        llm_summarizer: Optional[Callable[[str], str]] = None,
        source_root: Optional[Path] = None,
        filter_false_positives: bool = True,
        fp_discard_threshold: float = 0.7,
        future_state_rewriter: Optional[Callable[[Finding], Finding]] = None,
        economic_validator: Optional[Callable[[Finding], dict[str, Any]]] = None,
    ):
        self.db_path = db_path
        self.llm_summarizer = llm_summarizer
        self.source_root = source_root
        self.filter_false_positives = filter_false_positives
        self.fp_discard_threshold = fp_discard_threshold
        self.future_state_rewriter = future_state_rewriter
        self.economic_validator = economic_validator
        self.last_run_stats = PipelineRunStats()
        self.deduplicator = SARIFDeduplicator(line_tolerance=3)
        self.normalizer = RuleNormalizer()
        self.clusterer = (
            SemanticClusterer(embedding_model=embedding_model)
            if enable_semantic_clustering
            else None
        )
        self._init_db()

        self.adapters = {
            "aderyn": AderynAdapter(),
            "mythril": MythrilAdapter(),
            "halmos": HalmosAdapter(),
        }

    @property
    def last_validation_stats(self) -> PipelineRunStats:
        """Backward-compatible alias for CLI/reporting."""
        return self.last_run_stats

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                dedup_key TEXT PRIMARY KEY,
                tool TEXT,
                rule_id TEXT,
                normalized_category TEXT,
                swc TEXT,
                cwe TEXT,
                file_path TEXT,
                start_line INTEGER,
                message TEXT,
                cluster_id INTEGER,
                cluster_summary TEXT,
                properties TEXT,
                source_context TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def process(
        self,
        sarif_files: Dict[str, Path] | None = None,
        tool_outputs: Dict[str, Dict | List] | None = None,
        enable_llm_summaries: bool = False,
        filter_false_positives: bool | None = None,
    ) -> List[EnrichedFinding]:
        stats = PipelineRunStats()

        findings = self._stage_ingest(sarif_files, tool_outputs)
        findings = self._stage_future_state(findings)
        stats.ingested = len(findings)
        if not findings:
            self.last_run_stats = stats
            return []

        norm_map = self._stage_normalize(findings)

        unique = self._stage_deduplicate(findings)
        stats.after_dedup = len(unique)

        do_filter = self.filter_false_positives if filter_false_positives is None else filter_false_positives
        unique, filter_stats = self._stage_signal_filter(unique, apply_filter=do_filter)
        stats.signal_discarded = filter_stats["discarded"]
        stats.signal_promoted = filter_stats["promoted"]
        stats.signal_review = filter_stats["review"]

        unique, cluster_result = self._stage_cluster(unique)
        stats.clustered = len(unique)

        enriched = self._stage_enrich_and_persist(
            unique,
            norm_map,
            cluster_result,
            enable_llm_summaries=enable_llm_summaries,
        )
        stats.persisted = len(enriched)
        self.last_run_stats = stats
        return enriched

    def process_ensemble(
        self,
        tool_outputs: Dict[str, Any],
        enable_llm_summaries: bool = False,
        filter_false_positives: bool | None = None,
    ) -> List[EnrichedFinding]:
        return self.process(
            tool_outputs=tool_outputs,
            enable_llm_summaries=enable_llm_summaries,
            filter_false_positives=filter_false_positives,
        )

    def _stage_ingest(
        self,
        sarif_files: Dict[str, Path] | None,
        tool_outputs: Dict[str, Dict | List] | None,
    ) -> list[Finding]:
        all_findings: list[Finding] = []

        if sarif_files:
            for tool, path in sarif_files.items():
                all_findings.extend(parse_sarif(path, tool_name=tool))

        if tool_outputs:
            for tool_name, data in tool_outputs.items():
                adapter = self.adapters.get(tool_name.lower())
                if adapter:
                    all_findings.extend(adapter.parse(data))
                elif isinstance(data, dict) and is_sarif_payload(data):
                    all_findings.extend(parse_sarif(data, tool_name=tool_name))

        return all_findings

    def _stage_normalize(self, findings: list[Finding]) -> dict[int, NormalizedRule]:
        norm_map: dict[int, NormalizedRule] = {}
        for finding in findings:
            norm = self.normalizer.normalize(finding)
            norm_map[id(finding)] = norm
            finding.normalized = {
                "original_rule_id": norm.original_rule_id,
                "tool": norm.tool,
                "cwe": norm.cwe,
                "swc": norm.swc,
                "owasp": norm.owasp,
                "category": norm.category,
                "severity_hint": norm.severity_hint,
                "tags": norm.tags,
                "confidence": norm.confidence,
            }
        return norm_map

    def _stage_future_state(self, findings: list[Finding]) -> list[Finding]:
        if not self.future_state_rewriter:
            return findings
        rewritten: list[Finding] = []
        for finding in findings:
            try:
                rewritten.append(self.future_state_rewriter(finding))
            except Exception:
                rewritten.append(rewrite_finding(finding))
        return rewritten

    def _stage_deduplicate(self, findings: list[Finding]) -> list[Finding]:
        by_tool: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            by_tool[finding.tool].append(finding)
        return self.deduplicator.deduplicate_cross_tool(dict(by_tool)).unique_findings

    def _stage_signal_filter(
        self,
        findings: list[Finding],
        *,
        apply_filter: bool,
    ) -> tuple[list[Finding], dict[str, int]]:
        counts = {"discarded": 0, "promoted": 0, "review": 0}
        kept: list[Finding] = []

        for finding in findings:
            context = self._get_context(finding) if self.source_root else finding.snippet
            assessment = assess_signal_noise(finding, source_context=context)
            finding.properties["signal_filter"] = assessment

            if self.economic_validator:
                try:
                    economic_context = self.economic_validator(finding)
                    finding.properties["economic_context"] = economic_context
                    if isinstance(economic_context, dict):
                        finding.properties.setdefault("future_relevance_score", economic_context.get("future_relevance_score"))
                except Exception:
                    finding.properties.setdefault("economic_context", {})

            if self.economic_validator:
                try:
                    decision = validate_candidate(finding)
                    finding.properties["validation_bridge"] = decision.to_dict()
                    if decision.status == "promote":
                        assessment["suggested_action"] = "promote"
                        assessment["confidence"] = max(float(assessment.get("confidence", 0.0)), decision.confidence)
                except Exception:
                    pass

            action = assessment["suggested_action"]
            if action == "promote":
                counts["promoted"] += 1
            elif action == "discard" and apply_filter and should_drop_signal(
                assessment, threshold=self.fp_discard_threshold
            ):
                counts["discarded"] += 1
                continue
            else:
                counts["review"] += 1

            kept.append(finding)

        return kept, counts

    def _stage_cluster(
        self,
        findings: list[Finding],
    ) -> tuple[list[Finding], Optional[ClusterResult]]:
        if not self.clusterer or not findings:
            return findings, None
        cluster_result = self.clusterer.cluster(findings)
        self.clusterer.assign_clusters_to_findings(findings, cluster_result)
        return findings, cluster_result

    def _stage_enrich_and_persist(
        self,
        findings: list[Finding],
        norm_map: dict[int, NormalizedRule],
        cluster_result: Optional[ClusterResult],
        *,
        enable_llm_summaries: bool,
    ) -> list[EnrichedFinding]:
        enriched: list[EnrichedFinding] = []
        summaries = cluster_result.cluster_summaries if cluster_result else {}

        for finding in findings:
            norm = norm_map[id(finding)]
            context = self._get_context(finding) if self.source_root else None
            cluster_id = finding.properties.get("semantic_cluster", {}).get("cluster_id")
            base_summary = summaries.get(cluster_id, "") if cluster_id is not None else ""

            final_summary = base_summary
            if enable_llm_summaries and self.llm_summarizer and cluster_id is not None:
                prompt = self._build_anchor_summary_prompt(finding, cluster_id, base_summary)
                try:
                    final_summary = self.llm_summarizer(prompt)
                except Exception:
                    pass

            ef = EnrichedFinding(
                finding=finding,
                normalized=norm,
                source_context=context,
                dedup_key=self.deduplicator.key_strategy(finding),
                cluster_id=cluster_id,
                cluster_summary=final_summary,
            )
            enriched.append(ef)
            self._persist(ef)

        return enriched

    def _build_anchor_summary_prompt(self, finding: Finding, cluster_id: int, base: str) -> str:
        norm = finding.normalized or {}
        return f"""You are ANCHOR, the proof-gated bug hunting platform.

Cluster {cluster_id} contains semantically similar findings.
Representative finding:
- Tool: {finding.tool}
- Rule: {finding.rule_id}
- Message: {finding.message}
- Category: {norm.get('category', 'Unknown')}
- SWC: {norm.get('swc')}

Heuristic summary: {base}

Write a concise 2-4 sentence professional summary of the vulnerability pattern, common root cause in DeFi code, and recommended mitigation. Focus on impact and proof requirements."""

    def _get_context(self, finding: Finding, context_lines: int = 6) -> str:
        if not self.source_root:
            return ""
        try:
            p = self.source_root / finding.file_path.lstrip("./")
            if not p.exists():
                return ""
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            start = max(0, finding.start_line - 1 - context_lines)
            end = min(len(lines), finding.start_line + context_lines)
            return "\n".join(lines[start:end])
        except Exception:
            return ""

    def _persist(self, ef: EnrichedFinding):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                ef.dedup_key,
                ef.finding.tool,
                ef.finding.rule_id,
                ef.normalized.category,
                ef.normalized.swc,
                ef.normalized.cwe,
                ef.finding.file_path,
                ef.finding.start_line,
                ef.finding.message,
                ef.cluster_id,
                ef.cluster_summary,
                json.dumps(ef.finding.properties),
                ef.source_context,
                ef.processed_at,
            ),
        )
        conn.commit()
        conn.close()
