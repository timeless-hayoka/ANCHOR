"""Self-contained SARIF + multi-tool ensemble pipeline for ANCHOR."""

from __future__ import annotations

from .pipeline import EnrichedFinding, PipelineRunStats, SARIFProcessingPipeline
from .semantic_clusterer import ClusterResult, SemanticClusterer, semantic_clustering_available
from .future_state import FutureStateRewrite, rewrite_finding, rewrite_findings
from .economic_context import EconomicContextAssessment, assess_economic_context
from .validator_bridge import ValidationDecision, annotate_finding, validate_candidate
from .universe import UniverseComparison, compare_universes
from .drift import DriftResult, measure_drift
from .assumptions import AssumptionCard, extract_protocol_assumptions
from .mev_lifecycle import MevLifecycleReport, model_mev_lifecycle
from .incentive_surface import IncentiveSurfacePoint, map_incentive_surface
from .research_loop import ResearchLoopResult, ResearchQueueItem, build_research_loop
from .tuner import ClusterHyperparameterTuner
from .visualizer import visualize_semantic_clusters

__all__ = [
    "EnrichedFinding",
    "SARIFProcessingPipeline",
    "PipelineRunStats",
    "SemanticClusterer",
    "ClusterResult",
    "FutureStateRewrite",
    "rewrite_finding",
    "rewrite_findings",
    "EconomicContextAssessment",
    "assess_economic_context",
    "ValidationDecision",
    "annotate_finding",
    "validate_candidate",
    "UniverseComparison",
    "compare_universes",
    "DriftResult",
    "measure_drift",
    "AssumptionCard",
    "extract_protocol_assumptions",
    "MevLifecycleReport",
    "model_mev_lifecycle",
    "IncentiveSurfacePoint",
    "map_incentive_surface",
    "ResearchLoopResult",
    "ResearchQueueItem",
    "build_research_loop",
    "ClusterHyperparameterTuner",
    "visualize_semantic_clusters",
    "semantic_clustering_available",
]
