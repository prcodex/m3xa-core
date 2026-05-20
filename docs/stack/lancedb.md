# LanceDB

**Package:** `lancedb`  •  **Version pin:** `>=0.13.0`  •  **Role:** Vector database (single `unified_feed` table, vector + metadata)

## What it does

Embedded columnar vector database built on top of Apache Arrow + the Lance file format. m3xa-core uses it as a single-table store keyed by document id, with a 2048-dim vector column for similarity search and metadata columns for prefilters (domain, source, published_at, has_vector).

## Where it's used in m3xa-core

- `m3xa_core/backends/vector_db.py` — only place where `import lancedb` appears. `LanceDBBackend` implements the `VectorDBBackend` protocol. The retriever calls `search(query_vector=..., filter_expr="domain = 'brazil' AND has_vector = 1.0", top_k=N)`.
- `m3xa_core/cli.py` — opens the db path from CLI args.
- `examples/sample_corpus/` — minimal LanceDB table you can run the demo against without an external corpus.

## Why we picked it

- **Embedded.** No separate server, no docker-compose, no auth. Just a path on disk. Reference implementations should boot in one command.
- **Vector + metadata in one engine.** The retriever's filter expression (`domain = 'brazil' AND has_vector = 1.0`) is pushed down to the storage layer alongside the vector search — not done as a post-filter in Python.
- **Arrow-native.** Interop with pandas / polars / DuckDB is free. Useful when poking at the corpus during expertise authoring.
- **Versioned tables.** Lance's column-versioning means schema changes don't rewrite the whole dataset. Matters when you add a new metadata column to an existing corpus.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| Qdrant | Excellent product, but it's a server. Adding a docker dependency to a reference repo doubles the onboarding friction. |
| pgvector | Great when you already have Postgres. We don't — adding it just for this would be over-engineered for a library. |
| FAISS | No metadata filtering. Would force a post-filter pass that breaks at our corpus scale. |
| Weaviate / Pinecone / Chroma | Server-based or hosted. Same friction objection as Qdrant. |

## Schema (the `unified_feed` table)

Columns the backend relies on. Defined informally — see `examples/sample_corpus/build.py` for the script that creates the demo table:

| Column | Type | Notes |
|---|---|---|
| `id` | string | Unique row id |
| `text` | string | Chunk text indexed for retrieval |
| `source` | string | e.g. `bcb`, `xp`, `valor`, `bloomberg` |
| `published_at` | timestamp | UTC ISO-8601 |
| `domain` | string | `'brazil'` for everything in this repo |
| `content_vector` | list<float>(2048) | Voyage `voyage-3-large` output |
| `has_vector` | float | `1.0` if vector populated, `0.0` if pending. **Always filter on this** — vectorless rows leak otherwise. |

Schema drift between the repo and your corpus is the #1 cause of empty retrieval. Verify column names before assuming "the search is broken."

## How to swap it out

The contract is the `VectorDBBackend` Protocol in `m3xa_core/backends/vector_db.py`:

```python
class VectorDBBackend(Protocol):
    def search(self, *, query_vector: list[float], filter_expr: str,
               top_k: int) -> list[RetrievedDoc]: ...
```

Steps:

1. Implement the protocol around your DB (Qdrant, pgvector, etc.). Translate `filter_expr` into the equivalent in your engine — Qdrant payload filters, SQL WHERE, etc.
2. Pass it to `Pipeline(vector_db=your_backend, ...)`.
3. Re-index the corpus with the same vectors. The `RetrievedDoc` shape (`m3xa_core/schemas.py`) is what downstream actors expect; your backend must populate `id`, `text`, `source`, `published_at`, `score`, `domain`.

## Links

- Homepage: <https://lancedb.com>
- GitHub: <https://github.com/lancedb/lancedb>
- Docs: <https://lancedb.github.io/lancedb/>
- Lance file format: <https://lancedb.github.io/lance/>
- Last verified: 2026-05-19
