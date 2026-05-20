"""Actor 1 — Classifier. Tags a query with topics, entities, intent."""
from __future__ import annotations

from m3xa_core.schemas import ClassifierOutput


def classify(query: str, *, llm: object) -> ClassifierOutput:
    """Single Haiku call. Returns ClassifierOutput.

    Skeleton — see m3xabr-core for a reference implementation.
    """
    raise NotImplementedError
