"""Mind — runtime read of indexed LESSONS.md.

Reads the lessons_indexer output and lets the synthesizer pull a
relevant lesson into context when the query touches a known failure mode.
"""
from __future__ import annotations

from m3xa_core.self_awareness import lessons_indexer


def lessons_relevant_to(topics: list[str]) -> list[str]:
    """Return lesson bodies keyed on overlap with the provided topic tags.

    Deduplicates by lesson title — a lesson tagged with multiple of the
    queried topics is returned only once.
    """
    seen: set[str] = set()
    out: list[str] = []
    for topic in topics:
        for lesson in lessons_indexer.lessons_for_topic(topic):
            title = lesson.get("title", "")
            if title in seen:
                continue
            seen.add(title)
            out.append(lesson.get("body", ""))
    return out
