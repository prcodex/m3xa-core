"""Vector DB backend — pluggable.

Default uses LanceDB (single `unified_feed` table). Alternative
implementations could wrap Qdrant, Weaviate, pgvector, Pinecone.
"""
from __future__ import annotations

from typing import Any, Protocol

from m3xa_core.schemas import RetrievedDoc


class VectorDBBackend(Protocol):
    def search(
        self,
        *,
        query_vector: list[float],
        filter_expr: str,
        top_k: int,
    ) -> list[RetrievedDoc]: ...


class LanceDBBackend:
    """LanceDB backend.

    Expects a table named `unified_feed` with columns: id, text, source,
    published_at, domain, content_vector, has_vector, plus optional
    metadata. See docs/SCHEMA.md.
    """

    def __init__(self, db_path: str, table_name: str = "unified_feed") -> None:
        try:
            import lancedb
        except ImportError as e:
            raise ImportError(
                "lancedb package required. Install with: pip install lancedb"
            ) from e

        self._db = lancedb.connect(db_path)
        self._table_name = table_name
        try:
            self._table = self._db.open_table(table_name)
        except Exception:
            self._table = None

    def search(
        self,
        *,
        query_vector: list[float],
        filter_expr: str,
        top_k: int,
    ) -> list[RetrievedDoc]:
        if self._table is None:
            return []

        results = (
            self._table.search(query_vector)
            .where(filter_expr)
            .limit(top_k)
            .to_list()
        )
        return [self._row_to_doc(row) for row in results]

    @staticmethod
    def _row_to_doc(row: dict[str, Any]) -> RetrievedDoc:
        return RetrievedDoc(
            id=str(row.get("id", "")),
            text=str(row.get("text", "")),
            source=str(row.get("source", "unknown")),
            published_at=row.get("published_at"),
            score=float(row.get("_distance", 0.0)),
            domain=str(row.get("domain", "default")),
            metadata={
                k: v
                for k, v in row.items()
                if k not in {
                    "id", "text", "source", "published_at",
                    "domain", "content_vector", "_distance",
                }
            },
        )


class StubVectorDB:
    """Stub backend for tests."""

    def __init__(self, docs: list[RetrievedDoc] | None = None) -> None:
        self._docs = docs or []

    def add(self, doc: RetrievedDoc) -> None:
        self._docs.append(doc)

    def search(
        self,
        *,
        query_vector: list[float],
        filter_expr: str,
        top_k: int,
    ) -> list[RetrievedDoc]:
        wanted_domain = "default"
        if "domain = '" in filter_expr:
            wanted_domain = filter_expr.split("domain = '")[1].split("'")[0]
        filtered = [d for d in self._docs if d.domain == wanted_domain]
        return filtered[:top_k]
