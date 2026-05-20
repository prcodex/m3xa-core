"""Mind — runtime read of indexed LESSONS.md.

Reads the lessons_indexer output and lets the synthesizer pull a
relevant lesson into context when the query touches a known failure mode.
"""
from __future__ import annotations


def lessons_relevant_to(topics: list[str]) -> list[str]:
    """Return lessons keyed on overlap with provided topic tags. Skeleton."""
    raise NotImplementedError
