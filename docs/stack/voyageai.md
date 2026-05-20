# Voyage AI

**Package:** `voyageai`  •  **Version pin:** `>=0.3.0`  •  **Role:** Embeddings (`voyage-3-large`, 2048-dim, multilingual)

## What it does

Voyage AI's Python client for their embedding API. m3xa-core uses `voyage-3-large` at 2048 dimensions for every vector — both index-time (corpus ingestion lives outside this repo) and query-time (the retriever embeds the user query before LanceDB search).

## Where it's used in m3xa-core

- `m3xa_core/backends/embeddings.py` — only place where `import voyageai` appears. Wrapped in `VoyageEmbeddings`, implementing the `EmbeddingBackend` protocol. `input_type="query"` for `embed()`, `input_type="document"` for `embed_batch()`.
- `m3xa_core/cli.py` — reads `VOYAGE_API_KEY` and constructs `VoyageEmbeddings()` for the demo CLI.

## Why we picked it

- **Portuguese quality.** The corpus is Brazilian-Portuguese-heavy. Voyage-3-large performs noticeably better on cross-lingual retrieval than OpenAI's text-embedding-3-large at equivalent dimensions in our domain.
- **2048 dim sweet spot.** High enough that nearest-neighbor recall is solid for a small reference corpus (~10K rows in the example); low enough that LanceDB index build stays under a minute.
- **`input_type` distinction.** The query/document asymmetry is real and the SDK exposes it cleanly — we use it.
- **Pricing.** Among the cheapest commercial embedding APIs at this quality tier, and free-tier covers all of repo development.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| OpenAI `text-embedding-3-large` | Solid alternative, kept available as an extra (`m3xa-core[openai]`). 3072 dim is overkill for our corpus size. |
| Cohere `embed-multilingual-v3` | Available as `m3xa-core[cohere]`. Comparable quality but no Voyage-specific advantages disappeared. Kept as a swap option. |
| Local model (BGE-M3, multilingual-e5) | Removes API dependency but adds a GPU requirement to anyone running the demo. Not worth the friction for a reference implementation. |

## How to swap it out

The contract is the `EmbeddingBackend` Protocol in `m3xa_core/backends/embeddings.py`:

```python
class EmbeddingBackend(Protocol):
    dimension: int
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

Steps:

1. Implement the protocol (or use the bundled `OpenAIEmbeddings`/`StubEmbeddings`).
2. Pass it to `Pipeline(embeddings=your_backend, ...)`.
3. **Re-embed your corpus.** Vectors from different providers are not interchangeable; the LanceDB table must be rebuilt with the new model's output.

`dimension` is a contract field — it must match the table schema. See `docs/stack/lancedb.md` for how the table is laid out.

## Links

- Homepage: <https://www.voyageai.com>
- SDK on GitHub: <https://github.com/voyage-ai/voyageai-python>
- Docs: <https://docs.voyageai.com>
- Last verified: 2026-05-19
