# Cohere

**Package:** `cohere`  •  **Version pin:** `>=5.0.0`  •  **Extras group:** `m3xa-core[cohere]`  •  **Role:** Optional alternative embedding provider

## What it does

Cohere's Python SDK. Bundled as an optional extra so callers who already use Cohere can wire `embed-multilingual-v3` into the retriever without changing the rest of the pipeline.

## Where it's used in m3xa-core

No Cohere backend implementation is shipped yet — the SDK is reserved as a hook. Adding `CohereEmbeddings` in `m3xa_core/backends/embeddings.py` (following the same shape as `OpenAIEmbeddings`) is a one-class contribution.

## Why we picked it

- Strong multilingual embeddings, well-suited to Portuguese.
- Provides a second alternative beyond OpenAI so the "pluggable embeddings" claim has more than one credible swap.

## Alternatives considered

Covered in `docs/stack/voyageai.md`.

## How to swap it out

Once a `CohereEmbeddings` class exists, wire it like the OpenAI path:

```python
from m3xa_core.backends.embeddings import CohereEmbeddings
pipeline = Pipeline(embeddings=CohereEmbeddings(), ...)
```

Re-embed the corpus — see `docs/stack/voyageai.md`.

## Links

- Homepage: <https://cohere.com>
- SDK on GitHub: <https://github.com/cohere-ai/cohere-python>
- Last verified: 2026-05-19
