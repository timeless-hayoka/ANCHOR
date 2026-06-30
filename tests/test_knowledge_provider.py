from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


knowledge_provider = load_module("knowledge_provider", "knowledge_provider.py")


def test_list_topics_matches_manifest():
    provider = knowledge_provider.KnowledgeProvider(ROOT / "knowledge")
    topics = provider.list_topics()
    slugs = {topic.slug for topic in topics}
    assert "cloud_architecture" in slugs
    assert "sarif" in slugs
    assert "development_backlog" in slugs


def test_get_topic_returns_content():
    provider = knowledge_provider.KnowledgeProvider(ROOT / "knowledge")
    payload = provider.get("sarif")
    assert payload["topic"]["slug"] == "sarif"
    assert "SARIF" in payload["content"] or "sarif" in payload["content"].lower()


def test_search_finds_relevant_topic():
    provider = knowledge_provider.KnowledgeProvider(ROOT / "knowledge")
    hits = provider.search("confidence scoring", limit=3)
    assert hits
    assert any(hit.slug in {"zero_trust", "evidence_models", "development_backlog"} for hit in hits)


def test_refs_for_subsystem():
    provider = knowledge_provider.KnowledgeProvider(ROOT / "knowledge")
    refs = provider.refs_for_subsystem("sarif")
    slugs = {topic.slug for topic in refs}
    assert "sarif" in slugs


def test_unknown_slug_raises():
    provider = knowledge_provider.KnowledgeProvider(ROOT / "knowledge")
    try:
        provider.get("not-a-real-topic")
        assert False, "expected KeyError"
    except KeyError:
        pass
