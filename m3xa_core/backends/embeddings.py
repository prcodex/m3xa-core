"""Embedding backend — pluggable.

Default uses voyage-3-large (2048 dim, multilingual). Alternative
implementations: OpenAI, Cohere.
"""
from __future__ import annotations

import os
from typing import Protocol


class EmbeddingBackend(Protocol):
    """Minimal contract for an embedding provider."""

    dimension: int

    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class VoyageEmbeddings:
    """Voyage AI embedding backend."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "voyage-3-large",
        dimension: int = 2048,
    ) -> None:
        try:
            import voyageai
        except ImportError as e:
            raise ImportError(
                "voyageai package required. Install with: pip install voyageai"
            ) from e

        key = api_key or os.environ.get("VOYAGE_API_KEY")
        if not key:
            raise RuntimeError("VOYAGE_API_KEY not set.")

        self._client = voyageai.Client(api_key=key)
        self.model = model
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        result = self._client.embed(
            [text],
            model=self.model,
            input_type="query",
            output_dimension=self.dimension,
        )
        return result.embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(
            texts,
            model=self.model,
            input_type="document",
            output_dimension=self.dimension,
        )
        return result.embeddings


class StubEmbeddings:
    """Stub backend for tests. Deterministic vectors."""

    def __init__(self, dimension: int = 2048) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        h = hash(text)
        vec = [0.0] * self.dimension
        if self.dimension > 0:
            vec[abs(h) % self.dimension] = 1.0
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
