"""Deprecated: use anchor_sarif.fp_heuristics and SARIFProcessingPipeline stages instead.

Signal filtering is a pipeline stage (ingest → normalize → dedup → signal_filter → cluster → enrich).
ANCHOR is the only reasoning layer; no separate validator or LLM triage here.
"""

from __future__ import annotations

from .fp_heuristics import assess_signal_noise, should_drop_signal

__all__ = ["assess_signal_noise", "should_drop_signal"]
