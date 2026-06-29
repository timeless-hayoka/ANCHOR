"""Structured retrieval for the ANCHOR knowledge corpus."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KnowledgeTopic:
    slug: str
    title: str
    path: str
    subsystems: tuple[str, ...]
    tags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "path": self.path,
            "subsystems": list(self.subsystems),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class KnowledgeSearchHit:
    slug: str
    title: str
    path: str
    excerpt: str
    score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "path": self.path,
            "excerpt": self.excerpt,
            "score": self.score,
        }


class KnowledgeProvider:
    """Load and search repo-owned knowledge markdown by slug or query."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path(__file__).resolve().parent / "knowledge").resolve()
        self._manifest_path = self.root / "manifest.json"
        self._topics: list[KnowledgeTopic] | None = None

    def manifest(self) -> dict[str, Any]:
        if not self._manifest_path.is_file():
            return {"version": 0, "topics": []}
        return json.loads(self._manifest_path.read_text(encoding="utf-8"))

    def list_topics(self) -> list[KnowledgeTopic]:
        if self._topics is not None:
            return list(self._topics)
        topics: list[KnowledgeTopic] = []
        for row in self.manifest().get("topics", []):
            if not isinstance(row, dict) or not row.get("slug"):
                continue
            topics.append(
                KnowledgeTopic(
                    slug=str(row["slug"]),
                    title=str(row.get("title") or row["slug"]),
                    path=str(row.get("path") or f"{row['slug']}.md"),
                    subsystems=tuple(row.get("subsystems") or ()),
                    tags=tuple(row.get("tags") or ()),
                )
            )
        self._topics = topics
        return list(topics)

    def _topic_by_slug(self, slug: str) -> KnowledgeTopic | None:
        needle = slug.strip().lower().removesuffix(".md")
        for topic in self.list_topics():
            if topic.slug.lower() == needle:
                return topic
        return None

    def _resolve_path(self, topic: KnowledgeTopic) -> Path:
        candidate = (self.root / topic.path).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise ValueError(f"Knowledge path escapes corpus root: {topic.path}")
        return candidate

    def get(self, slug: str) -> dict[str, Any]:
        topic = self._topic_by_slug(slug)
        if topic is None:
            raise KeyError(slug)
        path = self._resolve_path(topic)
        if not path.is_file():
            raise FileNotFoundError(path)
        body = path.read_text(encoding="utf-8", errors="replace")
        return {"topic": topic.to_dict(), "path": str(path.relative_to(self.root)), "content": body}

    def refs_for_subsystem(self, subsystem: str) -> list[KnowledgeTopic]:
        needle = subsystem.strip().lower()
        return [t for t in self.list_topics() if needle in {s.lower() for s in t.subsystems}]

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeSearchHit]:
        pattern = (query or "").strip()
        if not pattern:
            return []
        limit = max(1, min(int(limit), 20))
        hits: list[KnowledgeSearchHit] = []

        rg_hits = self._rg_search(pattern, limit)
        if rg_hits:
            return rg_hits

        query_lower = pattern.lower()
        query_tokens = set(re.findall(r"[a-z0-9_+-]+", query_lower))

        for topic in self.list_topics():
            path = self._resolve_path(topic)
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            score = self._score_text(text, topic, query_lower, query_tokens)
            if score <= 0:
                continue
            excerpt = self._excerpt(text, query_lower)
            hits.append(
                KnowledgeSearchHit(
                    slug=topic.slug,
                    title=topic.title,
                    path=topic.path,
                    excerpt=excerpt,
                    score=score,
                )
            )

        hits.sort(key=lambda h: (-h.score, h.slug))
        return hits[:limit]

    def _rg_search(self, pattern: str, limit: int) -> list[KnowledgeSearchHit]:
        try:
            proc = subprocess.run(
                [
                    "rg",
                    "-i",
                    "-n",
                    "--no-heading",
                    "--max-count",
                    "1",
                    pattern,
                    str(self.root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return []
        if proc.returncode not in (0, 1) or not proc.stdout.strip():
            return []

        hits: list[KnowledgeSearchHit] = []
        for line in proc.stdout.splitlines():
            if len(hits) >= limit:
                break
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path = Path(parts[0])
            try:
                rel = file_path.relative_to(self.root)
            except ValueError:
                continue
            topic = self._topic_for_relative_path(str(rel))
            if topic is None:
                continue
            excerpt = parts[2].strip()
            hits.append(
                KnowledgeSearchHit(
                    slug=topic.slug,
                    title=topic.title,
                    path=topic.path,
                    excerpt=excerpt[:400],
                    score=100,
                )
            )
        return hits

    def _topic_for_relative_path(self, rel_path: str) -> KnowledgeTopic | None:
        normalized = rel_path.replace("\\", "/")
        for topic in self.list_topics():
            if topic.path.replace("\\", "/") == normalized:
                return topic
        return None

    @staticmethod
    def _score_text(
        text: str,
        topic: KnowledgeTopic,
        query_lower: str,
        query_tokens: set[str],
    ) -> int:
        hay = text.lower()
        score = 0
        if query_lower in hay:
            score += 10
        title_lower = topic.title.lower()
        if query_lower in title_lower:
            score += 8
        slug_lower = topic.slug.replace("_", " ")
        if query_lower in slug_lower:
            score += 6
        for tag in topic.tags:
            if query_lower in tag.lower():
                score += 4
        for subsystem in topic.subsystems:
            if query_lower in subsystem.lower():
                score += 3
        body_tokens = set(re.findall(r"[a-z0-9_+-]+", hay))
        overlap = len(query_tokens & body_tokens)
        score += overlap * 2
        return score

    @staticmethod
    def _excerpt(text: str, query_lower: str, radius: int = 120) -> str:
        hay = text.lower()
        idx = hay.find(query_lower)
        if idx < 0:
            snippet = text[: radius * 2].strip()
            return snippet + ("…" if len(text) > len(snippet) else "")
        start = max(0, idx - radius)
        end = min(len(text), idx + len(query_lower) + radius)
        chunk = text[start:end].replace("\n", " ").strip()
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""
        return f"{prefix}{chunk}{suffix}"


def render_topic_list(provider: KnowledgeProvider) -> str:
    lines = ["ANCHOR knowledge topics", ""]
    for topic in provider.list_topics():
        tags = ", ".join(topic.tags) if topic.tags else "—"
        subs = ", ".join(topic.subsystems) if topic.subsystems else "—"
        lines.append(f"- {topic.slug}: {topic.title}")
        lines.append(f"  subsystems: {subs} | tags: {tags}")
    return "\n".join(lines)


def render_search_results(hits: list[KnowledgeSearchHit]) -> str:
    if not hits:
        return "No knowledge matches."
    lines = ["Knowledge search results", ""]
    for hit in hits:
        lines.append(f"- [{hit.slug}] {hit.title} (score={hit.score})")
        lines.append(f"  {hit.excerpt}")
    return "\n".join(lines)
