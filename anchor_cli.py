#!/usr/bin/env python3
"""
ANCHOR CLI with full SARIF Intelligence integration.

Includes all original commands plus SARIF commands when anchor_sarif is available:
    anchor sarif process <files...>
    anchor sarif cluster
    anchor sarif tune
    anchor sarif visualize
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import runpy
import sys
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from github_discovery import (
    copy_selection,
    check_selected_repo_scope,
    run_selected_repo_hunt_plan,
    find_candidate,
    load_bundle,
    render_summary as render_github_discovery_summary,
    run_github_discovery,
    select_repo_from_latest_bundle,
)
from hunt_planner import build_hunt_plan, render_hunt_plan
from anchor_strategy import compute_strategy, render_strategy
from anchor_sarif import build_research_loop, rewrite_finding, assess_economic_context
from anchor_sarif.parser import Finding
from anchor_work_queue import load_work_queue, render_work_queue, work_queue_summary
from anchor_trends import compute_benchmark_trends, render_benchmark_trends
from bugbot.analysis import AnalysisConfig, render_analysis_report, run_target_analysis
from bugbot.scope import ANALYSIS, ScopeNotAuthorizedError, issue_scope_grant_from_confirmation, require_authorized_scope
from bugbot.trainer import BugBotTrainer
from bugbot.scenario_bridge import (
    archive_scenario_pack_run,
    build_scenario_pack_artifact,
    resolve_bounty_bot_dir,
    run_scenario_pack,
)
from knowledge_provider import (
    KnowledgeProvider,
    render_search_results,
    render_topic_list,
)

try:
    from anchor_sarif import (
        SARIFProcessingPipeline,
        SemanticClusterer,
        ClusterHyperparameterTuner,
        visualize_semantic_clusters,
    )
    HAS_SARIF = True
except ImportError:
    HAS_SARIF = False

MANIFEST_PATH = ROOT / "benchmarks" / "index.json"
OUTCOMES_DIR = ROOT / "outcomes"
OUTCOME_LEDGER_PATH = OUTCOMES_DIR / "ledger.jsonl"
DEFAULT_HISTORY_POLICY = {
    "artifact_retention": "keep_all_successful_runs",
    "manifest_default_tier": "development",
    "default_history_view": "published_only",
    "published_tier": "published",
    "note": "Successful development reruns remain on disk, but only intentionally promoted runs are first-class published artifacts.",
}
OUTCOME_TYPES = ["benchmark", "pr", "issue", "finding"]
OUTCOME_STATUSES = ["open", "published", "triaged", "accepted", "rejected", "patched", "merged"]
OUTCOME_LINK_KEYS = ["benchmark", "artifact", "pr", "issue", "report"]
LEGACY_STAGE_STATUS = {
    "benchmark_published": ("benchmark", "published"),
    "report_submitted": ("finding", "open"),
    "triaged": ("finding", "triaged"),
    "accepted": ("finding", "accepted"),
    "rejected": ("finding", "rejected"),
    "patched": ("finding", "patched"),
    "merged": ("pr", "merged"),
}
BENCHMARK_RUNNERS = {
    ("dvd", "phase1"): ROOT / "benchmarks" / "damn-vulnerable-defi" / "run_phase1_benchmark.py",
    ("ethernaut", "phase1"): ROOT / "benchmarks" / "ethernaut" / "run_phase1_benchmark.py",
    ("ethernaut", "source-comparison"): ROOT / "benchmarks" / "ethernaut" / "source-comparison" / "run_source_tool_comparison.py",
    ("sarif", "known-findings"): ROOT / "benchmarks" / "sarif-known-findings" / "run_known_findings_benchmark.py",
    ("defihacklabs", "source-comparison"): ROOT / "benchmarks" / "defihacklabs" / "source-comparison" / "run_source_tool_comparison.py",
}

GITHUB_CRAWLER_PROFILES = {
    "auth": {
        "command": "crawl-auth",
        "profile": "auth",
        "help": "Search GitHub for authorization-boundary bug surfaces",
    },
    "upgrade": {
        "command": "crawl-upgrade",
        "profile": "upgrade",
        "help": "Search GitHub for upgradeability and initializer bug surfaces",
    },
    "accounting": {
        "command": "crawl-accounting",
        "profile": "accounting",
        "help": "Search GitHub for accounting and rounding bug surfaces",
    },
    "oracle": {
        "command": "crawl-oracle",
        "profile": "oracle",
        "help": "Search GitHub for oracle and input-validation bug surfaces",
    },
    "external": {
        "command": "crawl-external",
        "profile": "external",
        "help": "Search GitHub for external-call and callback bug surfaces",
    },
}


def utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "entry").lower()).strip("-")
    return slug or "entry"


def make_outcome_id(entry_type: str, target: str) -> str:
    stamp = utcnow_iso().replace(":", "").replace("-", "")
    return f"{entry_type}-{safe_slug(target)}-{stamp}"


def _ensure_under_project_root(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{label} must stay under the approved project root: {ROOT}") from exc
    return candidate


def _resolve_project_path(raw: str | None, *, default: str | None = None, must_exist: bool = True, label: str = "path") -> Path | None:
    value = raw
    if value is None or not str(value).strip():
        if default is None:
            return None
        value = default
    candidate = _ensure_under_project_root(Path(str(value)), label)
    if must_exist and not candidate.exists():
        raise ValueError(f"{label} not found: {candidate}")
    return candidate


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anchor", description="ANCHOR local workflow entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    env_parser = sub.add_parser("env", help="Manage the local ANCHOR Python environment")
    env_sub = env_parser.add_subparsers(dest="env_command", required=True)
    env_init = env_sub.add_parser("init", help="Create a local .venv for ANCHOR")
    env_init.add_argument("--python", default=sys.executable, help="Python interpreter to use for the venv")

    benchmark_parser = sub.add_parser("benchmark", help="Run or inspect benchmark workflows")
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    benchmark_history = benchmark_sub.add_parser("history", help="Show benchmark history")
    benchmark_history.add_argument("--limit", type=int, default=10, help="Maximum number of entries to show")
    benchmark_history.add_argument("--all", action="store_true", help="Include development-tier reruns in addition to published artifacts")

    benchmark_compare = benchmark_sub.add_parser("compare", help="Compare two benchmark runs by manifest run id")
    benchmark_compare.add_argument("run_a")
    benchmark_compare.add_argument("run_b")

    benchmark_compare_source = benchmark_sub.add_parser("compare-source", help="Inspect a benchmark run's source-tool comparison")
    benchmark_compare_source.add_argument("run_id")
    benchmark_compare_source.add_argument("--json", action="store_true", help="Emit structured JSON instead of text")

    benchmark_latest = benchmark_sub.add_parser("latest", help="Show the latest published benchmark summary")

    benchmark_trends = benchmark_sub.add_parser(
        "trends",
        help="Historical trends from published benchmark runs (canonical trend source)",
    )
    benchmark_trends.add_argument("--limit", type=int, default=10, help="Maximum published runs to analyze")
    benchmark_trends.add_argument("--json", action="store_true", help="Emit structured JSON instead of text")

    benchmark_publish = benchmark_sub.add_parser("publish", help="Promote a run into first-class published benchmark history")
    benchmark_publish.add_argument("run_id")
    benchmark_publish.add_argument("--note", default="", help="Short publication note recorded in the manifest and outcome ledger")

    target_parsers = {}
    for target in sorted({key[0] for key in BENCHMARK_RUNNERS}):
        target_parser = benchmark_sub.add_parser(target, help=f"Benchmark workflows for {target}")
        level_sub = target_parser.add_subparsers(dest="level", required=True)
        target_parsers[target] = level_sub

    for target, level in sorted(BENCHMARK_RUNNERS):
        target_parsers[target].add_parser(level, help=f"Run the {level} benchmark for {target}")

    outcome_parser = sub.add_parser("outcome", help="Record and inspect real-world benchmark/report outcomes")
    outcome_sub = outcome_parser.add_subparsers(dest="outcome_command", required=True)

    outcome_history = outcome_sub.add_parser("history", help="Show recorded outcome ledger events")
    outcome_history.add_argument("--limit", type=int, default=10, help="Maximum number of outcome entries to show")

    outcome_summary = outcome_sub.add_parser("summary", help="Show compact outcome totals for dashboards and quick checks")
    outcome_summary.add_argument("--limit", type=int, default=5, help="Maximum number of recent lessons to show")

    outcome_insights = outcome_sub.add_parser("insights", help="Analyze outcome trends, repeated lessons, and target-level patterns")
    outcome_insights.add_argument("--limit", type=int, default=50, help="Maximum number of recent outcome entries to inspect")
    outcome_insights.add_argument("--top", type=int, default=5, help="Maximum number of top lessons and targets to show")

    outcome_add = outcome_sub.add_parser("add", help="Append a structured outcome event to the ledger")
    outcome_add.add_argument("--id", default="", help="Stable outcome entry id; generated automatically when omitted")
    outcome_add.add_argument("--type", required=True, choices=OUTCOME_TYPES, help="Outcome object type")
    outcome_add.add_argument("--target", required=True, help="Benchmark family, protocol, repository, or target label")
    outcome_add.add_argument("--status", required=True, choices=OUTCOME_STATUSES, help="Outcome status")
    outcome_add.add_argument("--evidence", default="", help="Evidence pointer such as a run id, PR URL, issue URL, artifact path, or report link")
    outcome_add.add_argument("--lesson", default="", help="What ANCHOR learned from this outcome")
    outcome_add.add_argument("--run-id", default="", help="Benchmark run id if applicable")
    outcome_add.add_argument("--benchmark-id", default="", help="Benchmark identifier if separate from run id")
    outcome_add.add_argument("--claim-id", default="", help="Claim identifier if applicable")
    outcome_add.add_argument("--case-id", default="", help="Case id if applicable")
    outcome_add.add_argument("--report-id", default="", help="External report or submission id if applicable")
    outcome_add.add_argument("--link-benchmark", default="", help="Link to a benchmark page or record")
    outcome_add.add_argument("--link-artifact", default="", help="Link to an artifact or evidence bundle")
    outcome_add.add_argument("--link-pr", default="", help="Link to a pull request")
    outcome_add.add_argument("--link-issue", default="", help="Link to an issue")
    outcome_add.add_argument("--link-report", default="", help="Link to an external report or submission")
    outcome_add.add_argument("--note", default="", help="Short note for the outcome event")

    outcome_record = outcome_sub.add_parser("record", help=argparse.SUPPRESS)
    for action in outcome_add._actions:
        if action.dest in {"help"}:
            continue
        kwargs = {
            "dest": action.dest,
            "default": action.default,
            "required": getattr(action, "required", False),
            "help": argparse.SUPPRESS,
        }
        if action.option_strings:
            if getattr(action, "choices", None) is not None:
                kwargs["choices"] = action.choices
            if getattr(action, "type", None) is not None:
                kwargs["type"] = action.type
            if getattr(action, "nargs", None) is not None:
                kwargs["nargs"] = action.nargs
            outcome_record.add_argument(*action.option_strings, **kwargs)

    strategy_parser = sub.add_parser("strategy", help="Evidence-driven hunt prioritization from trends and outcomes")
    strategy_parser.add_argument("--limit", type=int, default=10, help="Published benchmark runs for trend context")
    strategy_parser.add_argument("--top", type=int, default=5, help="Maximum ranked recommendations to include")
    strategy_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of text")

    work_parser = sub.add_parser("work", help="Inspect the canonical ANCHOR work queue")
    work_sub = work_parser.add_subparsers(dest="work_command", required=True)
    work_queue = work_sub.add_parser("queue", help="Render the repo-owned work queue document")
    work_queue.add_argument("--json", action="store_true", help="Emit structured JSON instead of text")

    knowledge_parser = sub.add_parser("knowledge", help="Browse structured ANCHOR reference documents")
    knowledge_sub = knowledge_parser.add_subparsers(dest="knowledge_command", required=True)
    knowledge_sub.add_parser("list", help="List registered knowledge topics")
    knowledge_show = knowledge_sub.add_parser("show", help="Show one topic by slug")
    knowledge_show.add_argument("slug", help="Topic slug (e.g. sarif, evidence_models)")
    knowledge_search = knowledge_sub.add_parser("search", help="Search the knowledge corpus")
    knowledge_search.add_argument("query", help="Search phrase")
    knowledge_search.add_argument("--limit", type=int, default=5, help="Maximum matches to return")
    knowledge_refs = knowledge_sub.add_parser("refs", help="Topics linked to a subsystem")
    knowledge_refs.add_argument("--subsystem", required=True, help="Subsystem name from manifest.json")

    codex_parser = sub.add_parser("codex", help="Codex integration helpers")
    codex_sub = codex_parser.add_subparsers(dest="codex_command", required=True)
    codex_mcp = codex_sub.add_parser("mcp", help="Run or register the local ANCHOR Codex MCP server")
    codex_group = codex_mcp.add_mutually_exclusive_group()
    codex_group.add_argument("--print-config", action="store_true", help="Print the Codex MCP registration JSON")
    codex_group.add_argument("--register", action="store_true", help="Run codex mcp add for the local ANCHOR server")
    codex_group.add_argument("--run", action="store_true", help="Run the ANCHOR MCP server directly")

    bugbot_parser = sub.add_parser("bugbot", help="BugBot training workflows")
    bugbot_sub = bugbot_parser.add_subparsers(dest="bugbot_command", required=True)
    bugbot_train = bugbot_sub.add_parser("train", help="Run a training session from a scenario file")
    bugbot_train.add_argument(
        "--scenario",
        required=True,
        help="Path to a scenario JSON file (e.g. scenarios/uups_initializer_takeover.json)",
    )
    bugbot_train.add_argument(
        "--strict-archive",
        action="store_true",
        help="Exit nonzero when knowledge archival fails (default: archival is non-fatal)",
    )
    bugbot_scope_check = bugbot_sub.add_parser(
        "scope-check",
        help="Validate scope confirmation evidence and write the active grant",
    )
    bugbot_scope_check.add_argument(
        "--confirmation",
        required=True,
        help="Path to scope_confirmation.md or .json with documented scope evidence",
    )
    bugbot_analyze = bugbot_sub.add_parser(
        "analyze",
        help="Run gated target analysis (requires active scope grant)",
    )
    bugbot_analyze.add_argument("--target-id", required=True, help="Selected target identifier")
    bugbot_analyze.add_argument("--target-ref", required=True, help="Exact repo commit or ref")
    bugbot_analyze.add_argument(
        "--repo-url",
        help="Git remote to clone when the analysis workspace does not exist yet",
    )
    bugbot_analyze.add_argument(
        "--workspace",
        help="Existing local workspace path (defaults to scope/analysis/<target-id>)",
    )
    bugbot_scenarios = bugbot_sub.add_parser(
        "scenarios",
        help="Run proof-backed BugBot curriculum in bounty-bot (requires Foundry)",
    )
    bugbot_scenarios.add_argument(
        "--all",
        action="store_true",
        help="Run all proof-ready scenarios via bounty-bot smoke",
    )
    bugbot_scenarios.add_argument(
        "--record",
        action="store_true",
        help="Append an outcome ledger entry for this run",
    )
    bugbot_scenarios.add_argument(
        "--json",
        action="store_true",
        help="Print the structured training artifact JSON to stdout",
    )

    if HAS_SARIF:
        sarif_parser = sub.add_parser("sarif", help="Process and analyze SARIF output from security tools")
        sarif_sub = sarif_parser.add_subparsers(dest="sarif_command", required=True)

        sarif_process = sarif_sub.add_parser("process", help="Parse, normalize, deduplicate & cluster SARIF files")
        sarif_process.add_argument("sarif_files", nargs="+", help="Path(s) to .sarif file(s)")
        sarif_process.add_argument("--db", default="anchor_sarif_findings.db", help="SQLite database to store results")
        sarif_process.add_argument("--llm", action="store_true", help="Enable LLM-powered cluster summarization")

        sarif_sub.add_parser("cluster", help="Run semantic clustering on stored findings")
        sarif_sub.add_parser("tune", help="Hyperparameter tuning for semantic clustering")

        sarif_research = sarif_sub.add_parser("research", help="Run the current hunt pipeline and show the combined research loop")
        sarif_research.add_argument("sarif_files", nargs="+", help="Path(s) to .sarif or tool JSON file(s)")
        sarif_research.add_argument("--db", default="anchor_sarif_findings.db", help="SQLite database to store results")
        sarif_research.add_argument("--future-state", default="ePBS + inclusion lists", help="Future-state label used for rewriting")
        sarif_research.add_argument("--llm", action="store_true", help="Enable LLM cluster summarization")

        sarif_visualize = sarif_sub.add_parser("visualize", help="Generate interactive UMAP visualization of clusters")
        sarif_visualize.add_argument("--output", default="sarif_clusters.html", help="Output HTML file")

    hunt_parser = sub.add_parser("hunt", help="Build or inspect a structured hunt plan")
    hunt_sub = hunt_parser.add_subparsers(dest="hunt_command", required=True)
    hunt_plan = hunt_sub.add_parser("plan", help="Build a falsifiable hunt plan from a target note")
    hunt_plan.add_argument("--target", required=True, help="Target note or markdown file inside the project root")
    hunt_plan.add_argument("--program", default="", help="Optional program or ecosystem label")
    hunt_plan.add_argument("--contract", default="", help="Optional contract or component name")
    hunt_plan.add_argument("--level", default="", help="Optional benchmark or scope level")
    hunt_plan.add_argument("--limit", type=int, default=5, help="Maximum strategy recommendations to consider")
    hunt_plan.add_argument("--json", action="store_true", help="Emit structured JSON instead of text")

    test_parser = sub.add_parser("test", help="Run the project test suite")
    test_parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Optional arguments forwarded to pytest")

    github_parser = sub.add_parser("github", help="Discover and curate GitHub repositories")
    github_sub = github_parser.add_subparsers(dest="github_command", required=True)
    github_crawl = github_sub.add_parser("crawl", help="Search GitHub and write a curated discovery bundle")
    github_crawl.add_argument("--query", action="append", default=[], help="GitHub search query. Repeatable. Defaults to the smart-contract security lane when omitted.")
    github_crawl.add_argument("--limit", type=int, default=12, help="Maximum number of repositories to keep in the bundle")
    github_crawl.add_argument("--per-query", type=int, default=25, help="Maximum search hits to inspect for each query")
    github_crawl.add_argument("--include-forks", action="store_true", help="Include forked repositories in the discovery pass")
    github_crawl.add_argument("--include-archived", action="store_true", help="Include archived repositories in the discovery pass")
    github_crawl.add_argument("--no-readmes", action="store_true", help="Skip README fetching and only use repository metadata")
    github_crawl.add_argument("--output-root", default=str(ROOT / "discoveries" / "github"), help="Folder where discovery bundles are written")
    github_crawl.add_argument("--json", action="store_true", help="Emit the bundle as JSON instead of text")
    for profile_config in GITHUB_CRAWLER_PROFILES.values():
        profile_parser = github_sub.add_parser(profile_config["command"], help=profile_config["help"])
        profile_parser.add_argument("--query", action="append", default=[], help="Optional extra GitHub search query. Repeatable.")
        profile_parser.add_argument("--limit", type=int, default=12, help="Maximum number of repositories to keep in the bundle")
        profile_parser.add_argument("--per-query", type=int, default=25, help="Maximum search hits to inspect for each query")
        profile_parser.add_argument("--include-forks", action="store_true", help="Include forked repositories in the discovery pass")
        profile_parser.add_argument("--include-archived", action="store_true", help="Include archived repositories in the discovery pass")
        profile_parser.add_argument("--no-readmes", action="store_true", help="Skip README fetching and only use repository metadata")
        profile_parser.add_argument("--output-root", default=str(ROOT / "discoveries" / "github"), help="Folder where discovery bundles are written")
        profile_parser.add_argument("--json", action="store_true", help="Emit the bundle as JSON instead of text")
    github_select = github_sub.add_parser("select", help="Copy a discovered repo into the human-approved queue")
    github_select.add_argument("repo", help="Repository full name to select, for example perimetersec/fuzzlib")
    github_select.add_argument("--output-root", default=str(ROOT / "discoveries" / "github"), help="Folder containing discovery bundles")
    github_select.add_argument("--run-id", default="", help="Optional discovery run id; newest run is used when omitted")
    github_select.add_argument("--json", action="store_true", help="Emit the selection record as JSON instead of text")
    github_plan = github_sub.add_parser("plan", help="Generate a constrained hunt plan for a selected repo")
    github_plan.add_argument("repo", help="Repository full name to plan for, for example perimetersec/fuzzlib")
    github_plan.add_argument("--output-root", default=str(ROOT / "discoveries" / "github"), help="Folder containing discovery bundles")
    github_plan.add_argument("--run-id", default="", help="Optional discovery run id; newest matching selection is used when omitted")
    github_plan.add_argument("--json", action="store_true", help="Emit the plan as JSON instead of text")
    github_scope = github_sub.add_parser("scope-check", help="Read scope_confirmation.md and block non-planning actions unless authorized")
    github_scope.add_argument("repo", help="Repository full name to check, for example perimetersec/fuzzlib")
    github_scope.add_argument("--output-root", default=str(ROOT / "discoveries" / "github"), help="Folder containing discovery bundles")
    github_scope.add_argument("--run-id", default="", help="Optional discovery run id; newest matching selection is used when omitted")
    github_scope.add_argument("--json", action="store_true", help="Emit the scope status as JSON instead of text")

    return parser


def load_manifest_payload() -> dict:
    if not MANIFEST_PATH.exists():
        return {"history_policy": dict(DEFAULT_HISTORY_POLICY), "benchmarks": []}
    payload = json.loads(MANIFEST_PATH.read_text())
    payload.setdefault("history_policy", dict(DEFAULT_HISTORY_POLICY))
    payload.setdefault("benchmarks", [])
    return payload


def save_manifest_payload(payload: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def load_manifest() -> list[dict]:
    return load_manifest_payload().get("benchmarks", [])


def benchmark_run_dir(entry: dict) -> Path | None:
    for key in ("record", "artifact_json", "storage_manifest"):
        value = entry.get(key)
        if not value:
            continue
        candidate = ROOT / value
        if candidate.is_dir():
            return candidate
        if candidate.name in {"README.md", "benchmark.json", "storage.json", "PUBLISHED.md"}:
            return candidate.parent
        return candidate.parent
    return None


def benchmark_tier(entry: dict) -> str:
    return entry.get("publication_tier", DEFAULT_HISTORY_POLICY["manifest_default_tier"])


def benchmark_display_key(entry: dict) -> tuple[int, float]:
    tier_rank = 0 if benchmark_tier(entry) == "published" else 1
    executed_at = str(entry.get("executed_at", ""))
    try:
        parsed = dt.datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
        timestamp = parsed.timestamp()
    except Exception:
        timestamp = float("-inf") if not executed_at else 0.0
    return (tier_rank, -timestamp)


def sorted_entries(entries: list[dict], reverse: bool = True) -> list[dict]:
    rows = sorted(entries, key=benchmark_display_key)
    if reverse:
        return rows
    return list(reversed(rows))


def find_entry(entries: list[dict], run_id: str) -> dict:
    for entry in entries:
        if entry.get("id") == run_id:
            return entry
    raise KeyError(run_id)


def metric_value(entry: dict, key: str) -> int | None:
    value = entry.get("results_summary", {}).get(key)
    return value if isinstance(value, int) else None


def format_delta(before: int | None, after: int | None) -> str:
    if before is None or after is None:
        return "n/a"
    delta = after - before
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def format_float_delta(before: float | int | None, after: float | int | None, places: int = 4) -> str:
    if before is None or after is None:
        return "n/a"
    delta = round(float(after) - float(before), places)
    if abs(delta) < 10 ** (-places):
        return "0"
    formatted = f"{delta:+.{places}f}".rstrip("0").rstrip(".")
    return formatted if formatted not in {"+0", "-0"} else "0"


def render_benchmark_history(entries: list[dict], limit: int = 10, include_development: bool = False) -> str:
    rows = sorted_entries(entries)
    if not include_development:
        rows = [entry for entry in rows if benchmark_tier(entry) == "published"]
    rows = rows[:limit]
    if not rows:
        scope = "published benchmark history" if not include_development else "benchmark history"
        return f"No {scope} available yet."

    headers = ["RUN ID", "TIER", "LEVEL", "PASS", "FAIL", "T/O", "SIG", "REL-HI", "CONF"]
    table = []
    for entry in rows:
        summary = entry.get("results_summary", {})
        table.append([
            entry.get("id", "unknown"),
            benchmark_tier(entry),
            entry.get("level", "—"),
            str(summary.get("passed", "—")),
            str(summary.get("failed", "—")),
            str(summary.get("timed_out", "—")),
            str(summary.get("detector_signals", "—")),
            str(summary.get("medium_high_target_relevant_findings", "—")),
            entry.get("confidence", "—"),
        ])

    widths = [len(header) for header in headers]
    for row in table:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def fmt(row: list[str]) -> str:
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row))

    lines = [fmt(headers), fmt(["-" * width for width in widths])]
    lines.extend(fmt(row) for row in table)
    return "\n".join(lines)


def render_benchmark_compare(entry_a: dict, entry_b: dict) -> str:
    compare = benchmark_compare_metrics(entry_a, entry_b)
    metrics_a = compare["metrics_a"]
    metrics_b = compare["metrics_b"]
    count_deltas = compare["count_deltas"]
    lines = [
        f"Comparing `{entry_a.get('id')}` -> `{entry_b.get('id')}`",
        "",
        "Metadata",
        f"- target: {entry_a.get('target', 'unknown')} -> {entry_b.get('target', 'unknown')}",
        f"- level: {entry_a.get('level', 'unknown')} -> {entry_b.get('level', 'unknown')}",
        f"- tier: {benchmark_tier(entry_a)} -> {benchmark_tier(entry_b)}",
        f"- executed_at: {entry_a.get('executed_at', 'unknown')} -> {entry_b.get('executed_at', 'unknown')}",
        f"- run_id: {metrics_a.get('run_id', entry_a.get('id', 'unknown'))} -> {metrics_b.get('run_id', entry_b.get('id', 'unknown'))}",
        f"- source_commit: {metrics_a.get('source_commit', 'unknown')} -> {metrics_b.get('source_commit', 'unknown')}",
        "",
        f"Guardrail: {compare['status']}",
    ]
    if compare["warnings"]:
        lines.append(f"- warnings: {', '.join(compare['warnings'])}")
    lines.extend([
        "",
        "Metrics deltas",
        f"- precision: {metrics_a.get('metrics', {}).get('precision', '—')} -> {metrics_b.get('metrics', {}).get('precision', '—')} (delta {format_float_delta(metrics_a.get('metrics', {}).get('precision'), metrics_b.get('metrics', {}).get('precision'))})",
        f"- recall: {metrics_a.get('metrics', {}).get('recall', '—')} -> {metrics_b.get('metrics', {}).get('recall', '—')} (delta {format_float_delta(metrics_a.get('metrics', {}).get('recall'), metrics_b.get('metrics', {}).get('recall'))})",
        f"- f1: {metrics_a.get('metrics', {}).get('f1', '—')} -> {metrics_b.get('metrics', {}).get('f1', '—')} (delta {format_float_delta(metrics_a.get('metrics', {}).get('f1'), metrics_b.get('metrics', {}).get('f1'))})",
        f"- runtime_seconds: {metrics_a.get('runtime_seconds', '—')} -> {metrics_b.get('runtime_seconds', '—')} (delta {format_float_delta(metrics_a.get('runtime_seconds'), metrics_b.get('runtime_seconds'))})",
        "",
        "Count deltas",
        f"- true_positive: {count_deltas['true_positive']:+d}",
        f"- false_positive: {count_deltas['false_positive']:+d}",
        f"- false_negative: {count_deltas['false_negative']:+d}",
        f"- true_negative: {count_deltas['true_negative']:+d}",
        f"- duplicates_removed: {count_deltas['duplicates_removed']:+d}",
        "",
        "Summary deltas",
    ])
    for key, label in [
        ("passed", "passed"),
        ("failed", "failed"),
        ("timed_out", "timed_out"),
        ("detector_signals", "detector_signals"),
        ("raw_detector_findings", "raw_detector_findings"),
        ("target_relevant_detector_findings", "target_relevant_detector_findings"),
        ("medium_high_target_relevant_findings", "medium_high_target_relevant_findings"),
    ]:
        before = metric_value(entry_a, key)
        after = metric_value(entry_b, key)
        lines.append(f"- {label}: {before if before is not None else '—'} -> {after if after is not None else '—'} (delta {format_delta(before, after)})")

    prov_a = entry_a.get("detector_provenance", {})
    prov_b = entry_b.get("detector_provenance", {})
    slither_a = prov_a.get("slither", {})
    slither_b = prov_b.get("slither", {})
    myth_a = prov_a.get("mythril", {})
    myth_b = prov_b.get("mythril", {})
    lines.extend([
        "",
        "Detector provenance",
        f"- slither: {slither_a.get('status', '—')} {slither_a.get('version', '')} -> {slither_b.get('status', '—')} {slither_b.get('version', '')}",
        f"- mythril: {myth_a.get('status', '—')} -> {myth_b.get('status', '—')}",
    ])
    return "\n".join(lines)


def find_latest_published_benchmark(entries: list[dict]) -> dict | None:
    published = [entry for entry in sorted_entries(entries) if benchmark_tier(entry) == "published"]
    return published[0] if published else None


def benchmark_regression_summary(current: dict, baseline: dict | None) -> dict[str, int]:
    current_results = benchmark_result_index(current)
    baseline_results = benchmark_result_index(baseline)

    resolved = 0
    regressions = 0
    environment_sensitive = 0
    stable = 0

    for challenge in sorted(set(baseline_results) | set(current_results)):
        current_result = current_results.get(challenge, {})
        baseline_result = baseline_results.get(challenge, {})
        current_status = str(current_result.get("status", current_result.get("reproduction_status", "unknown"))).upper()
        baseline_status = str(baseline_result.get("status", baseline_result.get("reproduction_status", "unknown"))).upper()
        if current_result.get("comparison") == "environment_sensitive" or baseline_result.get("comparison") == "environment_sensitive":
            environment_sensitive += 1
            continue
        if status_score(current_status) > status_score(baseline_status):
            resolved += 1
        elif status_score(current_status) < status_score(baseline_status):
            regressions += 1
        else:
            stable += 1

    return {
        "resolved": resolved,
        "regressions": regressions,
        "environment_sensitive": environment_sensitive,
        "stable": stable,
    }


def render_benchmark_latest(entry: dict | None, baseline: dict | None = None) -> str:
    if not entry:
        return "No published benchmark available yet."

    manifest = load_manifest()
    if baseline is None:
        baseline = find_previous_published_benchmark(manifest, entry.get("id", ""))
    summary = entry.get("results_summary", {}) or {}
    regression = benchmark_regression_summary(entry, baseline)
    regression_report = entry.get("regression_report", "")
    if not regression_report and benchmark_run_dir(entry) is not None:
        regression_report = str((benchmark_run_dir(entry) / "REGRESSION_REPORT.md").relative_to(ROOT))

    strategy = compute_strategy(
        manifest,
        load_outcome_entries(),
        root=ROOT,
        trends_limit=10,
        top_n=3,
    )
    future_state = (strategy.get("next_hunt") or {}).get("label", "ePBS + inclusion lists")
    research_loop = build_research_loop([_benchmark_latest_finding(entry, strategy, summary)], future_state=future_state)
    source_tool_compare = load_source_tool_compare(entry)
    source_tool_compare_report = source_tool_compare_report_path(entry)

    lines = [
        "Latest Published Benchmark",
        "",
        f"Run: {entry.get('id', 'unknown')}",
        f"Status: {benchmark_tier(entry)}",
        f"Level: {entry.get('level', 'unknown')}",
        f"Target: {entry.get('target', 'unknown')}",
        f"Executed At: {entry.get('executed_at', 'unknown')}",
        f"Confidence: {entry.get('confidence', '—')}",
        "",
        "Summary",
        f"- passed: {summary.get('passed', '—')}",
        f"- failed: {summary.get('failed', '—')}",
        f"- timed_out: {summary.get('timed_out', '—')}",
        f"- detector_signals: {summary.get('detector_signals', '—')}",
        f"- medium_high_target_relevant_findings: {summary.get('medium_high_target_relevant_findings', '—')}",
        "",
        "Source Tool Comparison",
        f"- source_tool: {source_tool_compare.get('source_tool', '—') if source_tool_compare else '—'}",
        f"- anchor_visible: {source_tool_compare.get('comparison', {}).get('anchor_visible', '—') if source_tool_compare else '—'}",
        f"- source_tool_visible: {source_tool_compare.get('comparison', {}).get('source_tool_visible', '—') if source_tool_compare else '—'}",
        f"- shared_visible: {source_tool_compare.get('comparison', {}).get('shared_visible', '—') if source_tool_compare else '—'}",
        f"- anchor_only: {source_tool_compare.get('comparison', {}).get('anchor_only', '—') if source_tool_compare else '—'}",
        f"- source_only: {source_tool_compare.get('comparison', {}).get('source_only', '—') if source_tool_compare else '—'}",
        f"- compare_report: {source_tool_compare_report or '—'}",
        "",
        "Regression",
        f"- resolved: {regression['resolved']}",
        f"- regressions: {regression['regressions']}",
        f"- environment_sensitive: {regression['environment_sensitive']}",
        f"- stable: {regression['stable']}",
        f"- report: {regression_report or '—'}",
        "",
        "Research Loop",
        f"- queue_depth: {len(research_loop.queue)}",
        f"- assumptions: {len(research_loop.assumption_cards)}",
        f"- universes: {len(research_loop.universe_report)}",
        f"- incentive_surface: {len(research_loop.incentive_surface)}",
        f"- mev_models: {len(research_loop.mev_reports)}",
        f"- top_queue: {research_loop.queue[0].title if research_loop.queue else '—'}",
    ]

    published_record = entry.get("published_record", "")
    storage_manifest = entry.get("storage_manifest", "")
    artifact_json = entry.get("artifact_json", "")
    if published_record or storage_manifest or artifact_json:
        lines.extend([
            "",
            "Artifacts",
            f"- published_record: {published_record or '—'}",
            f"- storage_manifest: {storage_manifest or '—'}",
            f"- artifact_json: {artifact_json or '—'}",
        ])

    lines.extend([
        "",
        "Use `anchor benchmark history` to compare this run against the published ledger.",
    ])
    return "\n".join(lines)

def parse_iso_timestamp(value: str) -> dt.datetime | None:
    if not value or value in {"unknown", ""}:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def load_benchmark_artifact(entry: dict | None) -> dict:
    if not entry:
        return {"results": [], "summary": {}}
    candidates = []
    for key in ("artifact_json", "record"):
        value = entry.get(key)
        if value:
            candidates.append(ROOT / value)
    run_dir = benchmark_run_dir(entry)
    if run_dir is not None:
        candidates.append(run_dir / "benchmark.json")
    for candidate in candidates:
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text())
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
    return {"results": [], "summary": entry.get("results_summary", {}) or {}}


def load_benchmark_metrics(entry: dict | None) -> dict:
    if not entry:
        return {
            "schema_version": "1.0",
            "benchmark": "unknown",
            "run_id": "unknown",
            "source_commit": "unknown",
            "counts": {
                "true_positive": 0,
                "false_positive": 0,
                "false_negative": 0,
                "true_negative": 0,
                "duplicates_removed": 0,
            },
            "metrics": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "runtime_seconds": 0,
            "tool_versions": {},
        }
    candidates = []
    value = entry.get("metrics_json")
    if value:
        candidates.append(ROOT / value)
    run_dir = benchmark_run_dir(entry)
    if run_dir is not None:
        candidates.append(run_dir / "metrics.json")
    for candidate in candidates:
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text())
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
    summary = entry.get("results_summary", {}) or {}
    return {
        "schema_version": "1.0",
        "benchmark": entry.get("target", "unknown"),
        "run_id": entry.get("id", "unknown"),
        "source_commit": entry.get("commit") or entry.get("source_commit") or "unknown",
        "counts": {
            "true_positive": summary.get("true_positives", 0),
            "false_positive": summary.get("false_positives", 0),
            "false_negative": summary.get("false_negatives", 0),
            "true_negative": summary.get("true_negatives", 0),
            "duplicates_removed": summary.get("duplicates_removed", 0),
        },
        "metrics": {
            "precision": summary.get("precision", 0.0),
            "recall": summary.get("recall", 0.0),
            "f1": summary.get("f1", 0.0),
        },
        "runtime_seconds": summary.get("runtime_seconds", 0) or 0,
        "tool_versions": {},
    }


def benchmark_compare_metrics(entry_a: dict, entry_b: dict) -> dict[str, object]:
    metrics_a = load_benchmark_metrics(entry_a)
    metrics_b = load_benchmark_metrics(entry_b)
    counts_a = metrics_a.get("counts", {}) or {}
    counts_b = metrics_b.get("counts", {}) or {}
    metrics_delta = {
        "precision": round(float(metrics_b.get("metrics", {}).get("precision", 0.0)) - float(metrics_a.get("metrics", {}).get("precision", 0.0)), 4),
        "recall": round(float(metrics_b.get("metrics", {}).get("recall", 0.0)) - float(metrics_a.get("metrics", {}).get("recall", 0.0)), 4),
        "f1": round(float(metrics_b.get("metrics", {}).get("f1", 0.0)) - float(metrics_a.get("metrics", {}).get("f1", 0.0)), 4),
    }
    count_keys = ["true_positive", "false_positive", "false_negative", "true_negative", "duplicates_removed"]
    count_deltas = {
        key: int(counts_b.get(key, 0)) - int(counts_a.get(key, 0))
        for key in count_keys
    }
    runtime_delta = float(metrics_b.get("runtime_seconds", 0) or 0) - float(metrics_a.get("runtime_seconds", 0) or 0)
    warnings = []
    if metrics_delta["precision"] < 0:
        warnings.append("precision dropped")
    if metrics_delta["f1"] < 0:
        warnings.append("f1 dropped")
    status = "FAIL" if metrics_delta["recall"] < 0 else ("WARN" if warnings else "PASS")
    return {
        "status": status,
        "warnings": warnings,
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
        "metrics_delta": metrics_delta,
        "count_deltas": count_deltas,
        "runtime_delta": round(runtime_delta, 4),
    }


def load_source_tool_compare(entry: dict | None) -> dict:
    if not entry:
        return {}
    candidates = []
    value = entry.get("source_tool_compare_json")
    if value:
        candidates.append(ROOT / value)
    run_dir = benchmark_run_dir(entry)
    if run_dir is not None:
        candidates.append(run_dir / "source_tool_compare.json")
    for candidate in candidates:
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text())
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
    return {}


def source_tool_compare_report_path(entry: dict | None) -> str:
    if not entry:
        return ""
    value = entry.get("source_tool_compare_json")
    if value:
        return str(value)
    run_dir = benchmark_run_dir(entry)
    if run_dir is not None:
        return str((run_dir / "source_tool_compare.json").relative_to(ROOT))
    return ""


def render_benchmark_source_tool_compare(compare: dict | None) -> str:
    if not compare:
        return "No source-tool comparison data available yet."
    comparison = compare.get("comparison", {}) or {}
    cases = compare.get("cases", []) or []
    lines = [
        "Source Tool Comparison",
        "",
        f"Run: {compare.get('run_id', 'unknown')}",
        f"Benchmark: {compare.get('benchmark', 'unknown')}",
        f"source_tool: {compare.get('source_tool', 'unknown')}",
        "",
        "Summary",
        f"- anchor_visible: {comparison.get('anchor_visible', '—')}",
        f"- source_tool_visible: {comparison.get('source_tool_visible', '—')}",
        f"- shared_visible: {comparison.get('shared_visible', '—')}",
        f"- anchor_only: {comparison.get('anchor_only', '—')}",
        f"- source_only: {comparison.get('source_only', '—')}",
        f"- shared_hidden: {comparison.get('shared_hidden', '—')}",
        f"- agreement: {comparison.get('agreement', '—')}",
        f"- visible_delta: {comparison.get('visible_delta', '—')}",
        "",
        "Cases",
    ]
    for case in cases:
        lines.extend([
            "",
            f"### {case.get('id', 'case')}",
            f"- anchor_visible: `{case.get('anchor_visible', '—')}`",
            f"- source_tool_visible: `{case.get('source_tool_visible', '—')}`",
            f"- comparison: `{case.get('comparison', '—')}`",
        ])
        if case.get("anchor_classification"):
            lines.append(f"- anchor_classification: `{case.get('anchor_classification')}`")
    return "\n".join(lines) + "\n"

def benchmark_result_index(entry: dict | None) -> dict[str, dict]:
    payload = load_benchmark_artifact(entry)
    index: dict[str, dict] = {}
    for result in payload.get("results", []) or []:
        challenge = result.get("challenge")
        if challenge:
            index[str(challenge)] = result
    return index


def status_score(value: str) -> int:
    return {
        "PASSED": 3,
        "SKIPPED": 2,
        "TIMED_OUT": 1,
        "FAILED": 0,
    }.get(value, -1)


def find_previous_published_benchmark(entries: list[dict], current_id: str) -> dict | None:
    published = [entry for entry in entries if benchmark_tier(entry) == "published" and entry.get("id") != current_id]
    if not published:
        return None
    current = next((entry for entry in entries if entry.get("id") == current_id), None)
    current_ts = parse_iso_timestamp(current.get("executed_at", "")) if current else None
    if current_ts is not None:
        older = [
            entry
            for entry in published
            if (parse_iso_timestamp(entry.get("executed_at", "")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)) < current_ts
        ]
        if older:
            return max(older, key=lambda entry: entry.get("executed_at", ""))
    return max(published, key=lambda entry: entry.get("executed_at", ""))


def render_benchmark_regression_report(current: dict, baseline: dict | None) -> str:
    current_payload = load_benchmark_artifact(current)
    baseline_payload = load_benchmark_artifact(baseline)
    current_results = benchmark_result_index(current)
    baseline_results = benchmark_result_index(baseline)
    current_summary = current_payload.get("summary", {}) or current.get("results_summary", {}) or {}
    baseline_summary = baseline_payload.get("summary", {}) or (baseline.get("results_summary", {}) if baseline else {}) or {}

    resolved = []
    regressions = []
    environment_sensitive = []
    stable = []
    all_challenges = sorted(set(baseline_results) | set(current_results))
    for challenge in all_challenges:
        current_result = current_results.get(challenge, {})
        baseline_result = baseline_results.get(challenge, {})
        current_status = str(current_result.get("status", current_result.get("reproduction_status", "unknown"))).upper()
        baseline_status = str(baseline_result.get("status", baseline_result.get("reproduction_status", "unknown"))).upper()
        if current_result.get("comparison") == "environment_sensitive" or baseline_result.get("comparison") == "environment_sensitive":
            environment_sensitive.append((challenge, baseline_status, current_status))
            continue
        if status_score(current_status) > status_score(baseline_status):
            resolved.append((challenge, baseline_status, current_status))
        elif status_score(current_status) < status_score(baseline_status):
            regressions.append((challenge, baseline_status, current_status))
        else:
            stable.append((challenge, baseline_status, current_status))

    lines = [
        f"# Benchmark Regression Report - {current.get('id', 'current')}",
        "",
        "## Baseline",
        f"- current run: `{current.get('id', 'unknown')}`",
        f"- current tier: `{benchmark_tier(current)}`",
        f"- current executed_at: `{current.get('executed_at', 'unknown')}`",
    ]
    if baseline:
        lines.extend([
            f"- baseline run: `{baseline.get('id', 'unknown')}`",
            f"- baseline tier: `{benchmark_tier(baseline)}`",
            f"- baseline executed_at: `{baseline.get('executed_at', 'unknown')}`",
        ])
    else:
        lines.append("- baseline run: none available")

    lines.extend([
        "",
        "## Summary",
        render_benchmark_compare(baseline or current, current),
        "",
        f"- resolved challenges: {len(resolved)}",
        f"- regressions: {len(regressions)}",
        f"- environment-sensitive: {len(environment_sensitive)}",
        f"- stable: {len(stable)}",
        "",
        "## Resolved",
    ])
    if resolved:
        for challenge, before, after in resolved:
            lines.append(f"- `{challenge}`: {before} -> {after}")
    else:
        lines.append("- none")

    lines.extend(["", "## Regressions"])
    if regressions:
        for challenge, before, after in regressions:
            lines.append(f"- `{challenge}`: {before} -> {after}")
    else:
        lines.append("- none")

    lines.extend(["", "## Environment-Sensitive"])
    if environment_sensitive:
        for challenge, before, after in environment_sensitive:
            lines.append(f"- `{challenge}`: {before} -> {after}")
    else:
        lines.append("- none")

    lines.extend(["", "## Metrics"])
    for key, label in [
        ("passed", "passed"),
        ("failed", "failed"),
        ("timed_out", "timed_out"),
        ("detector_signals", "detector_signals"),
        ("raw_detector_findings", "raw_detector_findings"),
        ("target_relevant_detector_findings", "target_relevant_detector_findings"),
        ("medium_high_target_relevant_findings", "medium_high_target_relevant_findings"),
    ]:
        before = baseline_summary.get(key) if isinstance(baseline_summary, dict) else None
        after = current_summary.get(key) if isinstance(current_summary, dict) else None
        lines.append(f"- {label}: {before if before is not None else '—'} -> {after if after is not None else '—'} (delta {format_delta(before, after)})")

    lines.extend([
        "",
        "## Notes",
        "- Published benchmark artifacts should cite `PUBLISHED.md` and this regression report together.",
        "- The report compares the newly published run against the most recent older published baseline.",
    ])
    return "\n".join(lines) + "\n"

def ensure_outcome_dir() -> None:
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)


def infer_outcome_type(entry: dict) -> str:
    if entry.get("type") in OUTCOME_TYPES:
        return entry["type"]
    stage = entry.get("stage", "")
    if stage in LEGACY_STAGE_STATUS:
        return LEGACY_STAGE_STATUS[stage][0]
    return "finding"


def infer_outcome_status(entry: dict) -> str:
    if entry.get("status") in OUTCOME_STATUSES:
        return entry["status"]
    stage = entry.get("stage", "")
    if stage in LEGACY_STAGE_STATUS:
        return LEGACY_STAGE_STATUS[stage][1]
    return "open"


def build_links(entry: dict) -> dict:
    links = dict(entry.get("links", {}) or {})
    legacy_mapping = {
        "benchmark": entry.get("link_benchmark"),
        "artifact": entry.get("link_artifact"),
        "pr": entry.get("link_pr"),
        "issue": entry.get("link_issue"),
        "report": entry.get("link_report"),
    }
    for key, value in legacy_mapping.items():
        if value and not links.get(key):
            links[key] = value
    return {key: links.get(key, "") for key in OUTCOME_LINK_KEYS}


def normalize_outcome_entry(entry: dict) -> dict:
    normalized = dict(entry)
    normalized.setdefault("timestamp", "unknown")
    normalized["type"] = infer_outcome_type(entry)
    normalized["status"] = infer_outcome_status(entry)
    normalized.setdefault("target", "")
    normalized.setdefault("run_id", "")
    normalized.setdefault("benchmark_id", normalized.get("run_id", ""))
    normalized.setdefault("claim_id", "")
    normalized.setdefault("case_id", "")
    normalized.setdefault("report_id", "")
    normalized.setdefault("note", "")
    normalized.setdefault("lesson", "")
    normalized.setdefault("evidence", "")
    normalized["links"] = build_links(normalized)
    if not normalized.get("id"):
        base = normalized.get("target") or normalized.get("type") or "entry"
        normalized["id"] = f"legacy-{safe_slug(base)}-{safe_slug(normalized.get('timestamp', 'unknown'))}"
    if not normalized["evidence"]:
        normalized["evidence"] = (
            normalized["links"].get("artifact")
            or normalized["links"].get("report")
            or normalized["links"].get("benchmark")
            or normalized.get("report_id")
            or normalized.get("run_id")
            or normalized.get("note", "")
        )
    return normalized


def load_outcome_entries() -> list[dict]:
    if not OUTCOME_LEDGER_PATH.exists():
        return []
    entries = []
    for line in OUTCOME_LEDGER_PATH.read_text().splitlines():
        if not line.strip():
            continue
        entries.append(normalize_outcome_entry(json.loads(line)))
    return entries


def append_outcome_entry(entry: dict) -> None:
    ensure_outcome_dir()
    with OUTCOME_LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def summarize_text(value: str, limit: int = 36) -> str:
    text = str(value or "—")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def outcome_display_key(entry: dict) -> tuple[int, float]:
    status = entry.get("status", "")
    type_ = entry.get("type", "")
    priority = 2
    if type_ == "benchmark" and status == "published":
        priority = 0
    elif type_ == "pr" and status == "merged":
        priority = 1
    timestamp = str(entry.get("timestamp", ""))
    try:
        parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        ts = parsed.timestamp()
    except Exception:
        ts = float("-inf") if not timestamp else 0.0
    return (priority, -ts)


def render_outcome_history(entries: list[dict], limit: int = 10) -> str:
    rows = sorted(entries, key=outcome_display_key)[:limit]
    if not rows:
        return "No outcome ledger entries recorded yet."

    headers = ["TIMESTAMP", "TYPE", "STATUS", "TARGET", "RUN ID", "REPORT", "LESSON"]
    table = []
    for entry in rows:
        table.append([
            entry.get("timestamp", "unknown"),
            entry.get("type", "unknown"),
            entry.get("status", "unknown"),
            entry.get("target", "—") or "—",
            entry.get("run_id", "—") or "—",
            entry.get("report_id", "—") or "—",
            summarize_text(entry.get("lesson", "") or entry.get("note", "—"), limit=42),
        ])

    widths = [len(header) for header in headers]
    for row in table:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def fmt(row: list[str]) -> str:
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row))

    lines = [fmt(headers), fmt(["-" * width for width in widths])]
    lines.extend(fmt(row) for row in table)
    return "\n".join(lines)


def render_outcome_summary(entries: list[dict], lesson_limit: int = 5) -> str:
    if not entries:
        return "No outcome ledger entries recorded yet."

    normalized = sorted(entries, key=lambda entry: entry.get("timestamp", ""), reverse=True)
    by_type = Counter(entry.get("type", "unknown") for entry in normalized)
    by_status = Counter(entry.get("status", "unknown") for entry in normalized)
    by_target = Counter(entry.get("target", "") or "unlabeled" for entry in normalized)

    lines = [
        "Outcome summary",
        f"- total events: {len(normalized)}",
        f"- status mix: " + ", ".join(f"{status}={by_status[status]}" for status in OUTCOME_STATUSES if by_status.get(status)),
        f"- type mix: " + ", ".join(f"{kind}={by_type[kind]}" for kind in OUTCOME_TYPES if by_type.get(kind)),
        "",
        "Top targets",
    ]
    for target, count in by_target.most_common(5):
        lines.append(f"- {target}: {count} event(s)")

    lessons = [entry for entry in normalized if entry.get("lesson")]
    lines.extend(["", "Recent lessons"])
    if not lessons:
        lines.append("- No lessons recorded yet.")
    else:
        for entry in lessons[:lesson_limit]:
            lines.append(f"- {entry.get('timestamp', 'unknown')} · {entry.get('target', 'unlabeled')}: {entry.get('lesson')}")

    return "\n".join(lines)


def render_outcome_insights(entries: list[dict], limit: int = 50, top_n: int = 5) -> str:
    if not entries:
        return "No outcome ledger entries recorded yet."

    from anchor_strategy import categorize_lesson, PATTERN_RECOMMENDATIONS

    rows = sorted(entries, key=lambda entry: entry.get("timestamp", ""), reverse=True)[:limit]
    by_status = Counter(entry.get("status", "unknown") for entry in rows)
    by_target = Counter(entry.get("target", "") or "unlabeled" for entry in rows)
    by_type = Counter(entry.get("type", "unknown") for entry in rows)
    lesson_counter = Counter((entry.get("lesson") or "").strip() for entry in rows if (entry.get("lesson") or "").strip())
    pattern_counter: Counter[str] = Counter()
    for entry in rows:
        lesson = (entry.get("lesson") or entry.get("note") or "").strip()
        if lesson:
            pattern_counter[categorize_lesson(lesson)] += 1

    lines = [
        f"Last {len(rows)} outcomes",
        "",
        "Status mix",
    ]
    for status in OUTCOME_STATUSES:
        if by_status.get(status):
            lines.append(f"- {status}: {by_status[status]}")
    lines.extend(["", "Type mix"])
    for kind in OUTCOME_TYPES:
        if by_type.get(kind):
            lines.append(f"- {kind}: {by_type[kind]}")
    lines.extend(["", "Lessons learned (grouped)"])
    if pattern_counter:
        for label, count in pattern_counter.most_common(top_n):
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- No lessons recorded yet.")
    top_pattern = pattern_counter.most_common(1)[0][0] if pattern_counter else None
    if top_pattern and top_pattern not in {"Other", "Uncategorized"}:
        lines.extend(["", "Common failure pattern", "", top_pattern, ""])
        recommendation = PATTERN_RECOMMENDATIONS.get(top_pattern, "")
        if recommendation:
            lines.extend(["Recommendation", "", recommendation, ""])
    lines.extend(["", "Top lessons (verbatim)"])
    if lesson_counter:
        for lesson, count in lesson_counter.most_common(top_n):
            lines.append(f"- {lesson} ({count})")
    else:
        lines.append("- No lessons recorded yet.")
    lines.extend(["", "Top targets"])
    for target, count in by_target.most_common(top_n):
        lines.append(f"- {target}: {count}")
    return "\n".join(lines)


def build_outcome_entry_from_args(args: argparse.Namespace) -> dict:
    links = {
        "benchmark": args.link_benchmark,
        "artifact": args.link_artifact,
        "pr": args.link_pr,
        "issue": args.link_issue,
        "report": args.link_report,
    }
    entry = {
        "id": args.id or make_outcome_id(args.type, args.target),
        "timestamp": utcnow_iso(),
        "type": args.type,
        "status": args.status,
        "target": args.target,
        "run_id": args.run_id,
        "benchmark_id": args.benchmark_id or args.run_id,
        "claim_id": args.claim_id,
        "case_id": args.case_id,
        "report_id": args.report_id,
        "evidence": args.evidence,
        "lesson": args.lesson,
        "note": args.note,
        "links": links,
    }
    return normalize_outcome_entry(entry)




def _benchmark_latest_finding(entry: dict, strategy: dict, summary: dict) -> Finding:
    next_hunt = strategy.get("next_hunt") or {}
    return Finding(
        tool="anchor",
        rule_id=str(entry.get("id") or "benchmark-latest"),
        level=str(entry.get("confidence") or "note"),
        message=str(next_hunt.get("reason") or entry.get("title") or entry.get("id") or "benchmark"),
        file_path=str(entry.get("target") or "benchmark"),
        start_line=1,
        properties={
            "benchmark_id": entry.get("id"),
            "benchmark_target": entry.get("target"),
            "benchmark_summary": dict(summary or {}),
            "source": "anchor_cli.render_benchmark_latest",
        },
    )
def cmd_env_init(args: argparse.Namespace) -> int:
    venv_dir = ROOT / ".venv"
    subprocess.run([args.python, "-m", "venv", str(venv_dir)], check=True)
    pip_path = venv_dir / "bin" / "pip"
    requirements = ROOT / "requirements.txt"
    print(f"Created virtual environment at {venv_dir}")
    print(f"To finish setup, run: {pip_path} install -r {requirements}")
    return 0


def cmd_benchmark_history(args: argparse.Namespace) -> int:
    print(render_benchmark_history(load_manifest(), limit=args.limit, include_development=args.all))
    return 0


def cmd_benchmark_compare(args: argparse.Namespace) -> int:
    entries = load_manifest()
    try:
        entry_a = find_entry(entries, args.run_a)
        entry_b = find_entry(entries, args.run_b)
    except KeyError as exc:
        print(f"Unknown run id: {exc.args[0]}", file=sys.stderr)
        return 1
    compare = benchmark_compare_metrics(entry_a, entry_b)
    print(render_benchmark_compare(entry_a, entry_b))
    return 1 if compare["status"] == "FAIL" else 0


def cmd_benchmark_latest(args: argparse.Namespace) -> int:
    del args
    print(render_benchmark_latest(find_latest_published_benchmark(load_manifest())))
    return 0


def cmd_benchmark_trends(args: argparse.Namespace) -> int:
    trends = compute_benchmark_trends(load_manifest(), root=ROOT, limit=args.limit)
    if args.json:
        print(json.dumps(trends, indent=2))
    else:
        print(render_benchmark_trends(trends))
    return 0


def cmd_strategy(args: argparse.Namespace) -> int:
    payload = compute_strategy(
        load_manifest(),
        load_outcome_entries(),
        root=ROOT,
        trends_limit=args.limit,
        top_n=args.top,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_strategy(payload))
    return 0


def cmd_work_queue(args: argparse.Namespace) -> int:
    queue = load_work_queue()
    if args.json:
        print(json.dumps(work_queue_summary(queue), indent=2))
    else:
        print(render_work_queue(queue))
    return 0


def _knowledge_provider() -> KnowledgeProvider:
    return KnowledgeProvider(ROOT / "knowledge")


def load_training_scenarios(scenario_path: Path) -> list[dict]:
    """Load one or more scenario dicts from a JSON file."""
    payload = json.loads(scenario_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        if not payload:
            raise ValueError("scenario file contains an empty list")
        return payload
    if isinstance(payload, dict):
        nested = payload.get("scenarios")
        if nested is not None:
            if not isinstance(nested, list) or not nested:
                raise ValueError("scenario file 'scenarios' must be a non-empty list")
            return nested
        if payload.get("id"):
            return [payload]
    raise ValueError("scenario file must be a scenario object, a list, or {\"scenarios\": [...]}")


def cmd_bugbot_scope_check(args: argparse.Namespace) -> int:
    result = issue_scope_grant_from_confirmation(Path(args.confirmation))
    if result.success:
        print(f"Scope grant active: {result.grant_path}")
        return 0
    print(f"Scope check failed: {result.reason}", file=sys.stderr)
    return 1


def cmd_bugbot_analyze(args: argparse.Namespace) -> int:
    try:
        grant = require_authorized_scope(
            target_id=args.target_id,
            target_ref=args.target_ref,
            action=ANALYSIS,
        )
    except ScopeNotAuthorizedError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    workspace = Path(args.workspace).resolve() if args.workspace else None
    result = run_target_analysis(
        AnalysisConfig(
            target_id=args.target_id,
            target_ref=args.target_ref,
            grant=grant,
            repo_url=args.repo_url,
            workspace=workspace,
            anchor_root=ROOT,
        )
    )
    print(render_analysis_report(result))
    return 0 if result.success else 1


def cmd_bugbot_scenarios(args: argparse.Namespace) -> int:
    if not args.all:
        print("Specify --all to run the proof-backed BugBot scenario pack.", file=sys.stderr)
        return 2

    try:
        bounty_bot_dir = resolve_bounty_bot_dir(anchor_root=ROOT)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        result = run_scenario_pack(bounty_bot_dir=bounty_bot_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if result.output:
        print(result.output)
    elif result.exit_code != 0:
        print("BugBot scenario pack failed with no output.", file=sys.stderr)

    artifact = archive_scenario_pack_run(
        anchor_root=ROOT,
        run=result,
        record_outcome=bool(args.record),
        append_outcome=append_outcome_entry,
        utcnow_iso=utcnow_iso,
        make_outcome_id=make_outcome_id,
    )
    print(f"Artifact: {artifact.relative_to(ROOT)}")

    if args.json:
        print(json.dumps(json.loads(artifact.read_text(encoding="utf-8")), indent=2))

    return result.exit_code


def cmd_bugbot_train(args: argparse.Namespace) -> int:
    scenario_path = Path(args.scenario)
    if not scenario_path.is_absolute():
        scenario_path = (ROOT / scenario_path).resolve()
    if not scenario_path.is_file():
        print(f"Scenario file not found: {scenario_path}", file=sys.stderr)
        return 1

    try:
        scenarios = load_training_scenarios(scenario_path)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"Failed to load scenario: {exc}", file=sys.stderr)
        return 1

    trainer = BugBotTrainer(strict_archive=args.strict_archive)
    try:
        result = trainer.train(scenarios)
    except RuntimeError as exc:
        print(f"Training: FAIL", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    status = "PASS" if result.success else "FAIL"
    print(f"Training: {status}")
    print(f"Scenarios: {result.scenarios_passed}/{result.scenarios_processed} passed")
    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)

    archive = result.archive
    if archive is None:
        print("Archive: skipped")
    elif archive.success:
        rel = archive.path
        if rel is not None:
            try:
                rel = rel.relative_to(ROOT)
            except ValueError:
                pass
            print(f"Archive: {rel}")
        else:
            print("Archive: ok")
    else:
        print(f"Archive: FAILED ({archive.error})", file=sys.stderr)

    if not result.success:
        return 1
    if args.strict_archive and archive is not None and not archive.success:
        return 1
    return 0


def cmd_knowledge_list(args: argparse.Namespace) -> int:
    provider = _knowledge_provider()
    topics = [topic.to_dict() for topic in provider.list_topics()]
    if getattr(args, "json", False):
        print(json.dumps({"topics": topics}, indent=2))
    else:
        print(render_topic_list(provider))
    return 0


def cmd_knowledge_show(args: argparse.Namespace) -> int:
    provider = _knowledge_provider()
    try:
        payload = provider.get(args.slug)
    except KeyError:
        print(f"Unknown knowledge topic: {args.slug}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Knowledge file missing: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        topic = payload["topic"]
        print(f"# {topic['title']} ({topic['slug']})")
        print()
        print(payload["content"])
    return 0


def cmd_knowledge_search(args: argparse.Namespace) -> int:
    provider = _knowledge_provider()
    hits = provider.search(args.query, limit=args.limit)
    if getattr(args, "json", False):
        print(json.dumps({"query": args.query, "hits": [hit.to_dict() for hit in hits]}, indent=2))
    else:
        print(render_search_results(hits))
    return 0


def cmd_knowledge_refs(args: argparse.Namespace) -> int:
    provider = _knowledge_provider()
    topics = provider.refs_for_subsystem(args.subsystem)
    if getattr(args, "json", False):
        print(json.dumps({"subsystem": args.subsystem, "topics": [topic.to_dict() for topic in topics]}, indent=2))
    else:
        if not topics:
            print(f"No knowledge topics for subsystem: {args.subsystem}")
        else:
            print(f"Knowledge refs for subsystem: {args.subsystem}")
            for topic in topics:
                print(f"- {topic.slug}: {topic.title}")
    return 0


def cmd_benchmark_compare_source(args: argparse.Namespace) -> int:
    entries = load_manifest()
    try:
        entry = find_entry(entries, args.run_id)
    except KeyError as exc:
        print(f"Unknown run id: {exc.args[0]}", file=sys.stderr)
        return 1
    compare = load_source_tool_compare(entry)
    if not compare:
        print(f"No source-tool comparison data for run id: {args.run_id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(compare, indent=2))
    else:
        print(render_benchmark_source_tool_compare(compare))
    return 0


def cmd_hunt_plan(args: argparse.Namespace) -> int:
    target_path = _resolve_project_path(args.target, must_exist=True, label="target note")
    assert target_path is not None
    payload = build_hunt_plan(
        target_path=target_path,
        root=ROOT,
        benchmark_entries=load_manifest(),
        outcome_entries=load_outcome_entries(),
        program=args.program or None,
        contract=args.contract or None,
        level=args.level or None,
        top_n=args.limit,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_hunt_plan(payload))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    pytest_args = args.pytest_args or []
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    command = [sys.executable, "-m", "pytest", "-q", *pytest_args]
    try:
        completed = subprocess.run(command, cwd=ROOT)
    except FileNotFoundError:
        print("Python runtime not found.", file=sys.stderr)
        return 1
    if completed.returncode != 0:
        print("pytest is not installed or the test run failed. Install dev deps with: python3 -m pip install -r requirements-dev.txt", file=sys.stderr)
    return completed.returncode


def cmd_github_crawl(args: argparse.Namespace) -> int:
    try:
        bundle, run_dir = run_github_discovery(
            args.query,
            limit=args.limit,
            per_query=args.per_query,
            include_forks=args.include_forks,
            include_archived=args.include_archived,
            fetch_readmes=not args.no_readmes,
            output_root=Path(args.output_root),
        )
    except Exception as exc:
        print(f"GitHub discovery failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(bundle, indent=2))
    else:
        print(render_github_discovery_summary(bundle, run_dir=run_dir))
        print(f"\nDiscovery bundle written to: {run_dir}")
    return 0


def cmd_github_profile_crawl(args: argparse.Namespace, profile: str) -> int:
    try:
        bundle, run_dir = run_github_discovery(
            args.query or None,
            profile=profile,
            limit=args.limit,
            per_query=args.per_query,
            include_forks=args.include_forks,
            include_archived=args.include_archived,
            fetch_readmes=not args.no_readmes,
            output_root=Path(args.output_root),
        )
    except Exception as exc:
        print(f"GitHub discovery failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(bundle, indent=2))
    else:
        print(render_github_discovery_summary(bundle, run_dir=run_dir))
        print(f"\nDiscovery bundle written to: {run_dir}")
    return 0


def cmd_github_select(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root)
    try:
        if args.run_id:
            run_dir = output_root / args.run_id
            if not run_dir.exists():
                print(f"Discovery run not found: {run_dir}", file=sys.stderr)
                return 1
            bundle = load_bundle(run_dir)
            candidate = find_candidate(bundle, args.repo)
            selected_dir = copy_selection(candidate, run_dir, run_dir / "selected")
        else:
            run_dir, selected_dir = select_repo_from_latest_bundle(args.repo, output_root=output_root)
    except Exception as exc:
        print(f"GitHub selection failed: {exc}", file=sys.stderr)
        return 1

    selection_record = json.loads((selected_dir / "selection.json").read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(selection_record, indent=2))
    else:
        print(f"Selected {args.repo} from {run_dir.name}")
        print(f"Queue directory: {selected_dir}")
        print(f"Approval record: {selected_dir / 'selection.json'}")
    return 0


def cmd_github_plan(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root)
    try:
        payload, run_dir, selected_dir = run_selected_repo_hunt_plan(
            args.repo,
            output_root=output_root,
            run_id=args.run_id or None,
        )
    except Exception as exc:
        print(f"GitHub hunt plan generation failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Generated constrained hunt plan for {args.repo}")
        print(f"Discovery run: {run_dir.name}")
        print("Selected layout:")
        rel_selected = str(selected_dir.relative_to(ROOT)) if selected_dir.is_relative_to(ROOT) else str(selected_dir)
        print(f"- {rel_selected}/")
        print("  - candidate.json")
        print("  - summary.md")
        print("  - selection.json")
        print("  - scope_confirmation.md")
        print("  - hunt_plan.md")
    return 0


def cmd_github_scope_check(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root)
    try:
        run_dir, selected_dir, scope = check_selected_repo_scope(
            args.repo,
            output_root=output_root,
            run_id=args.run_id or None,
        )
    except Exception as exc:
        print(f"GitHub scope check failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(scope, indent=2))
    else:
        print(f"Scope status: {scope['scope_status']}")
        print(f"Reason: {scope['reason']}")
        print(f"Allowed actions: {scope['allowed_actions']}")
        print(f"Scope file: {selected_dir / 'scope_confirmation.md'}")
        print(f"Discovery run: {run_dir.name}")
    return 0


def cmd_benchmark_publish(args: argparse.Namespace) -> int:
    payload = load_manifest_payload()
    entries = payload.get("benchmarks", [])
    try:
        entry = find_entry(entries, args.run_id)
    except KeyError:
        print(f"Unknown run id: {args.run_id}", file=sys.stderr)
        return 1

    published_at = utcnow_iso()
    previous_published = find_previous_published_benchmark(entries, entry.get("id", ""))
    entry["publication_tier"] = "published"
    entry["status"] = "published"
    entry["published_at"] = published_at
    if args.note:
        entry["publication_note"] = args.note

    run_dir = benchmark_run_dir(entry)
    published_record = None
    regression_report = None
    if run_dir and run_dir.exists():
        storage_path = run_dir / "storage.json"
        if storage_path.exists():
            try:
                storage_payload = json.loads(storage_path.read_text())
                if isinstance(storage_payload, dict):
                    storage_payload["status"] = "published"
                    storage_payload["published_at"] = published_at
                    storage_payload["publication_note"] = args.note or "Published benchmark artifact"
                    storage_path.write_text(json.dumps(storage_payload, indent=2) + "\n", encoding="utf-8")
                    entry["storage_manifest"] = str(storage_path.relative_to(ROOT))
                    entry["storage_status"] = "published"
            except Exception:
                pass
        published_record_path = run_dir / "PUBLISHED.md"
        published_record_path.write_text(
            "# Published Benchmark Run\n\n"
            f"- Benchmark ID: `{entry.get('id', '')}`\n"
            f"- Published at: `{published_at}`\n"
            f"- Tier: `published`\n"
            f"- Status: `{entry.get('status', 'published')}`\n"
            f"- Note: `{args.note or 'Published benchmark artifact'}`\n"
            f"- Benchmark record: `{entry.get('record', '')}`\n"
            f"- Benchmark artifact: `{entry.get('artifact_json', '')}`\n"
            f"- Storage manifest: `{entry.get('storage_manifest', '')}`\n\n"
            "This file marks the promoted artifact that should be cited by default.\n",
            encoding="utf-8",
        )
        published_record = str(published_record_path.relative_to(ROOT))
        entry["published_record"] = published_record

        regression_report_path = run_dir / "REGRESSION_REPORT.md"
        regression_report_path.write_text(
            render_benchmark_regression_report(entry, previous_published),
            encoding="utf-8",
        )
        regression_report = str(regression_report_path.relative_to(ROOT))
        entry["regression_report"] = regression_report

    save_manifest_payload(payload)
    append_outcome_entry(normalize_outcome_entry({
        "id": make_outcome_id("benchmark", entry.get("id", "benchmark")),
        "timestamp": published_at,
        "type": "benchmark",
        "status": "published",
        "stage": "benchmark_published",
        "target": entry.get("target", ""),
        "run_id": entry.get("id", ""),
        "benchmark_id": entry.get("id", ""),
        "claim_id": "",
        "case_id": "",
        "report_id": "",
        "evidence": regression_report or published_record or entry.get("record", "") or entry.get("artifact_json", ""),
        "lesson": "",
        "note": args.note or "Published benchmark artifact",
        "links": {
            "benchmark": entry.get("record", ""),
            "artifact": published_record or entry.get("artifact_json", ""),
            "pr": "",
            "issue": "",
            "report": regression_report or "",
        },
    }))
    print(f"Published benchmark run: {entry.get('id')}")
    return 0

def cmd_benchmark_run(target: str, level: str) -> int:
    runner = BENCHMARK_RUNNERS[(target, level)]
    try:
        runpy.run_path(str(runner), run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1


def cmd_outcome_history(args: argparse.Namespace) -> int:
    print(render_outcome_history(load_outcome_entries(), limit=args.limit))
    return 0


def cmd_outcome_summary(args: argparse.Namespace) -> int:
    print(render_outcome_summary(load_outcome_entries(), lesson_limit=args.limit))
    return 0


def cmd_outcome_insights(args: argparse.Namespace) -> int:
    print(render_outcome_insights(load_outcome_entries(), limit=args.limit, top_n=args.top))
    return 0


def cmd_outcome_add(args: argparse.Namespace) -> int:
    entry = build_outcome_entry_from_args(args)
    append_outcome_entry(entry)
    print(f"Recorded outcome event: {entry['type']} {entry['status']}")
    return 0


def cmd_sarif_process(args: argparse.Namespace) -> int:
    if not HAS_SARIF:
        print("anchor_sarif package not found. Make sure anchor_sarif/ is in the same directory.", file=sys.stderr)
        return 1

    sarif_map = {Path(path).stem: Path(path) for path in args.sarif_files}
    pipeline = SARIFProcessingPipeline(
        db_path=Path(args.db),
        enable_semantic_clustering=True,
    )
    enriched = pipeline.process(sarif_map, enable_llm_summaries=args.llm)
    print(f"Processed {len(enriched)} unique findings")
    print(f"Results saved to: {args.db}")
    return 0


def cmd_sarif_cluster(args: argparse.Namespace) -> int:
    del args
    if not HAS_SARIF:
        print("anchor_sarif not available", file=sys.stderr)
        return 1
    print("Semantic clustering on existing database is available via the Python API.")
    print("Example: from anchor_sarif import SemanticClusterer")
    return 0


def cmd_sarif_tune(args: argparse.Namespace) -> int:
    del args
    if not HAS_SARIF:
        print("anchor_sarif not available", file=sys.stderr)
        return 1
    print("Hyperparameter tuning example ready. Use ClusterHyperparameterTuner in Python.")
    return 0


def cmd_sarif_visualize(args: argparse.Namespace) -> int:
    if not HAS_SARIF:
        print("anchor_sarif not available", file=sys.stderr)
        return 1
    print(f"Visualization will be written to {args.output}")
    return 0


def cmd_sarif_research(args: argparse.Namespace) -> int:
    if not HAS_SARIF:
        print("anchor_sarif package not found. Make sure anchor_sarif/ is in the same directory.", file=sys.stderr)
        return 1

    sarif_map = {Path(path).stem: Path(path) for path in args.sarif_files}
    pipeline = SARIFProcessingPipeline(
        db_path=Path(args.db),
        enable_semantic_clustering=True,
        future_state_rewriter=lambda finding: rewrite_finding(finding, future_state=args.future_state),
        economic_validator=lambda finding: assess_economic_context(finding, future_state=args.future_state).to_dict(),
    )
    enriched = pipeline.process(sarif_map, enable_llm_summaries=args.llm)
    research = build_research_loop([item.finding for item in enriched], future_state=args.future_state)
    payload = research.to_dict()
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        top = payload["queue"][0] if payload["queue"] else None
        print("ANCHOR Research Loop")
        print(f"- rewritten findings: {payload['rewritten_findings']}")
        print(f"- assumptions: {len(payload['assumption_cards'])}")
        print(f"- universe comparisons: {len(payload['universe_report'])}")
        print(f"- incentive surface points: {len(payload['incentive_surface'])}")
        if top:
            print(f"- top queue item: {top['title']} (priority {top['priority']})")
    return 0


def cmd_codex_mcp(args: argparse.Namespace) -> int:
    launcher = ROOT / "scripts" / "codex_mcp_launcher.py"
    cmd = [sys.executable, str(launcher)]
    if args.print_config:
        cmd.append("--print-config")
    elif args.register:
        cmd.append("--register")
    elif args.run:
        cmd.append("--run")
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "env" and args.env_command == "init":
        return cmd_env_init(args)
    if args.command == "benchmark" and args.benchmark_command == "history":
        return cmd_benchmark_history(args)
    if args.command == "benchmark" and args.benchmark_command == "compare":
        return cmd_benchmark_compare(args)
    if args.command == "benchmark" and args.benchmark_command == "compare-source":
        return cmd_benchmark_compare_source(args)
    if args.command == "benchmark" and args.benchmark_command == "latest":
        return cmd_benchmark_latest(args)
    if args.command == "benchmark" and args.benchmark_command == "trends":
        return cmd_benchmark_trends(args)
    if args.command == "strategy":
        return cmd_strategy(args)
    if args.command == "work" and args.work_command == "queue":
        return cmd_work_queue(args)
    if args.command == "knowledge" and args.knowledge_command == "list":
        return cmd_knowledge_list(args)
    if args.command == "knowledge" and args.knowledge_command == "show":
        return cmd_knowledge_show(args)
    if args.command == "knowledge" and args.knowledge_command == "search":
        return cmd_knowledge_search(args)
    if args.command == "knowledge" and args.knowledge_command == "refs":
        return cmd_knowledge_refs(args)
    if args.command == "codex" and args.codex_command == "mcp":
        return cmd_codex_mcp(args)
    if args.command == "bugbot" and args.bugbot_command == "train":
        return cmd_bugbot_train(args)
    if args.command == "bugbot" and args.bugbot_command == "scope-check":
        return cmd_bugbot_scope_check(args)
    if args.command == "bugbot" and args.bugbot_command == "analyze":
        return cmd_bugbot_analyze(args)
    if args.command == "bugbot" and args.bugbot_command == "scenarios":
        return cmd_bugbot_scenarios(args)
    if args.command == "hunt" and args.hunt_command == "plan":
        return cmd_hunt_plan(args)
    if args.command == "test":
        return cmd_test(args)
    if args.command == "github" and args.github_command == "crawl":
        return cmd_github_crawl(args)
    if args.command == "github" and args.github_command in {config["command"] for config in GITHUB_CRAWLER_PROFILES.values()}:
        profile = next(config["profile"] for config in GITHUB_CRAWLER_PROFILES.values() if config["command"] == args.github_command)
        return cmd_github_profile_crawl(args, profile)
    if args.command == "github" and args.github_command == "select":
        return cmd_github_select(args)
    if args.command == "github" and args.github_command == "plan":
        return cmd_github_plan(args)
    if args.command == "github" and args.github_command == "scope-check":
        return cmd_github_scope_check(args)
    if args.command == "benchmark" and args.benchmark_command == "publish":
        return cmd_benchmark_publish(args)
    if args.command == "benchmark":
        return cmd_benchmark_run(args.benchmark_command, args.level)
    if args.command == "outcome" and args.outcome_command == "history":
        return cmd_outcome_history(args)
    if args.command == "outcome" and args.outcome_command == "summary":
        return cmd_outcome_summary(args)
    if args.command == "outcome" and args.outcome_command == "insights":
        return cmd_outcome_insights(args)
    if args.command == "outcome" and args.outcome_command in {"add", "record"}:
        return cmd_outcome_add(args)
    if args.command == "sarif":
        if args.sarif_command == "process":
            return cmd_sarif_process(args)
        if args.sarif_command == "cluster":
            return cmd_sarif_cluster(args)
        if args.sarif_command == "tune":
            return cmd_sarif_tune(args)
        if args.sarif_command == "research":
            return cmd_sarif_research(args)
        if args.sarif_command == "visualize":
            return cmd_sarif_visualize(args)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
