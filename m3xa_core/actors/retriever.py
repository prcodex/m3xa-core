"""Actor 4 — Retriever. Vector search over unified_feed + entity boost reranking.

Reads ClassifierOutput for entities + time_window_hours. Builds the filter
expression for the VectorDBBackend, runs the search, applies the
institution-boost reranking from concepts/institution_boost.md.
"""
from __future__ import annotations

from m3xa_core.schemas import ClassifierOutput, RetrievedDoc


def retrieve(
    classifier_output: ClassifierOutput,
    *,
    embeddings: object,
    vector_db: object,
    top_k: int = 20,
) -> list[RetrievedDoc]:
    """Vector search + entity boost. Skeleton."""
    raise NotImplementedError
