"""SARIF subcommands for ANCHOR CLI.

Usage:
    python -m anchor_sarif.cli process slither.json aderyn.json --ensemble
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .parser import is_sarif_payload, parse_sarif
from .pipeline import SARIFProcessingPipeline
from .research_loop import build_research_loop
from .future_state import rewrite_finding
from .economic_context import assess_economic_context


def _infer_tool_name(path: Path) -> str:
    stem = path.stem.lower()
    for tool in ("aderyn", "mythril", "halmos", "slither", "codeql", "semgrep"):
        if tool in stem:
            return tool
    return stem


def _load_tool_output(path: Path) -> tuple[str, dict | list]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tool = _infer_tool_name(path)
    if is_sarif_payload(payload):
        return tool, payload
    return tool, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANCHOR SARIF Intelligence CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="Process SARIF or tool JSON files")
    process_parser.add_argument("files", nargs="+", help="SARIF or tool JSON files")
    process_parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Treat files as outputs from different tools (Aderyn, Mythril, etc.)",
    )
    process_parser.add_argument("--db", default="anchor_sarif_findings.db")
    process_parser.add_argument("--llm", action="store_true", help="Enable LLM cluster summarization")
    process_parser.add_argument("--source-root", default=None, help="Repo root for source context enrichment")
    process_parser.add_argument(
        "--filter-false-positives",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Discard high-confidence false positives before clustering (default: enabled)",
    )
    process_parser.add_argument(
        "--fp-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for auto-discarding false positives",
    )

    research_parser = subparsers.add_parser("research", help="Run the research loop over a set of files")
    research_parser.add_argument("files", nargs="+", help="SARIF or tool JSON files")
    research_parser.add_argument("--db", default="anchor_sarif_findings.db")
    research_parser.add_argument("--future-state", default="ePBS + inclusion lists")
    research_parser.add_argument("--llm", action="store_true", help="Enable LLM cluster summarization")

    visualize_parser = subparsers.add_parser("visualize", help="Generate UMAP visualization from DB")
    visualize_parser.add_argument("--db", default="anchor_sarif_findings.db")
    visualize_parser.add_argument("--output", default="sarif_clusters.html")

    args = parser.parse_args(argv)
    pipeline = SARIFProcessingPipeline(
        db_path=Path(args.db),
        source_root=Path(args.source_root) if getattr(args, "source_root", None) else None,
        filter_false_positives=args.filter_false_positives,
        fp_discard_threshold=args.fp_threshold,
    )

    if args.command == "process":
        if args.ensemble:
            tool_outputs: dict[str, dict | list] = {}
            for file_path in args.files:
                path = Path(file_path)
                tool, payload = _load_tool_output(path)
                tool_outputs[tool] = payload
            enriched = pipeline.process_ensemble(
                tool_outputs,
                enable_llm_summaries=args.llm,
                filter_false_positives=args.filter_false_positives,
            )
        else:
            sarif_map: dict[str, Path] = {}
            tool_outputs: dict[str, dict | list] = {}
            for file_path in args.files:
                path = Path(file_path)
                payload = json.loads(path.read_text(encoding="utf-8"))
                tool = _infer_tool_name(path)
                if is_sarif_payload(payload):
                    sarif_map[tool] = path
                else:
                    tool_outputs[tool] = payload
            enriched = pipeline.process(
                sarif_files=sarif_map or None,
                tool_outputs=tool_outputs or None,
                enable_llm_summaries=args.llm,
                filter_false_positives=args.filter_false_positives,
            )
        stats = pipeline.last_run_stats
        if stats.after_dedup:
            pct = round(stats.signal_discard_rate * 100, 1)
            print(
                f"Pipeline: {stats.ingested} ingested → {stats.after_dedup} deduped → "
                f"{stats.signal_discarded} signal-discarded ({pct}%), "
                f"{stats.persisted} persisted"
            )
        print(f"Processed {len(enriched)} findings into {args.db}")
        return 0

    if args.command == "research":
        pipeline = SARIFProcessingPipeline(
            db_path=Path(args.db),
            future_state_rewriter=lambda finding: rewrite_finding(finding, future_state=args.future_state),
            economic_validator=lambda finding: assess_economic_context(finding, future_state=args.future_state).to_dict(),
        )
        tool_outputs = {}
        sarif_map = {}
        for file_path in args.files:
            path = Path(file_path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            tool = _infer_tool_name(path)
            if is_sarif_payload(payload):
                sarif_map[tool] = path
            else:
                tool_outputs[tool] = payload
        enriched = pipeline.process(sarif_files=sarif_map or None, tool_outputs=tool_outputs or None, enable_llm_summaries=args.llm)
        research = build_research_loop([item.finding for item in enriched], future_state=args.future_state)
        print(json.dumps(research.to_dict(), indent=2))
        return 0

    if args.command == "visualize":
        try:
            from .visualizer import visualize_semantic_clusters
            from .semantic_clusterer import SemanticClusterer, semantic_clustering_available
        except ImportError:
            print("Visualization dependencies not installed.", file=sys.stderr)
            return 1

        if not semantic_clustering_available():
            print("Semantic clustering dependencies not installed.", file=sys.stderr)
            return 1

        import sqlite3

        conn = sqlite3.connect(args.db)
        rows = conn.execute(
            "SELECT tool, rule_id, message, file_path, start_line, properties, cluster_id FROM findings"
        ).fetchall()
        conn.close()

        if not rows:
            print(f"No findings in {args.db}", file=sys.stderr)
            return 1

        from .parser import Finding

        findings: list[Finding] = []
        labels = []
        for tool, rule_id, message, file_path, start_line, properties_json, cluster_id in rows:
            props = json.loads(properties_json) if properties_json else {}
            findings.append(
                Finding(
                    tool=tool,
                    rule_id=rule_id,
                    level="warning",
                    message=message,
                    file_path=file_path,
                    start_line=int(start_line or 0),
                    properties=props,
                )
            )
            labels.append(int(cluster_id) if cluster_id is not None else -1)

        import numpy as np
        from .semantic_clusterer import ClusterResult

        cluster_result = ClusterResult(
            cluster_labels=np.array(labels),
            n_clusters=len({label for label in labels if label != -1}),
        )
        fig = visualize_semantic_clusters(findings, cluster_result)
        fig.write_html(args.output)
        print(f"Visualization written to {args.output}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
