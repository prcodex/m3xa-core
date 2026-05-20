"""The 7-actor query pipeline — orchestrator.

Each actor is a small, testable module under m3xa_core/actors/. The
pipeline runs them in sequence; see BODY.md for the actor inventory.

Self-awareness components (m3xa_core/self_awareness/) are *not* part of
the pipeline — they run alongside it, reading the pipeline's outputs.
"""
from __future__ import annotations

from m3xa_core.schemas import PipelineResult


class Pipeline:
    """Composes the 7 actors into a single callable.

    Construction takes backend objects (LLM, embeddings, vector DB) so
    each can be swapped independently — see m3xa_core/backends/.

    This is a skeleton. The full implementation wires the actors together;
    see m3xabr-core for a reference of the same shape, narrower scope.
    """

    def __init__(
        self,
        *,
        lancedb_path: str | None = None,
        llm: object | None = None,
        embeddings: object | None = None,
        vector_db: object | None = None,
    ) -> None:
        self.lancedb_path = lancedb_path
        self.llm = llm
        self.embeddings = embeddings
        self.vector_db = vector_db

    def run(self, query: str) -> PipelineResult:
        """Run the 7-actor pipeline against a query.

        Returns PipelineResult — see m3xa_core/schemas.py for the shape.

        Skeleton: see TODO in the implementation.
        """
        raise NotImplementedError(
            "Pipeline.run is a skeleton in m3xa-core 0.1. "
            "See m3xabr-core for a reference implementation of the same shape."
        )
