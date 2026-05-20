"""lessons_indexer — LESSONS.md → tagged JSON for runtime retrieval.

Parses LESSONS.md, tags each lesson by the domain(s) it applies to, and
writes a JSON index at .m3xa/lessons_index.json. The synthesizer can
pull a relevant lesson into context when the query touches a known
failure mode.
"""
from __future__ import annotations


def rebuild_index() -> int:
    """Re-parse LESSONS.md and rewrite the index. Returns lesson count.

    Skeleton.
    """
    raise NotImplementedError


def lessons_for_topic(topic: str) -> list[dict]:
    """Return lessons relevant to a topic. Skeleton."""
    raise NotImplementedError
