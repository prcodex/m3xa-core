# OpenAI

**Package:** `openai`  •  **Version pin:** `>=1.30.0`  •  **Extras group:** `m3xa-core[openai]`  •  **Role:** Optional alternative LLM + embedding provider

## What it does

Official OpenAI Python SDK. Bundled as an **optional extra** — not installed by default. Provides an alternative path if the caller prefers GPT-4o for synthesis or `text-embedding-3-large` for vectors.

## Where it's used in m3xa-core

- `m3xa_core/backends/embeddings.py` — `OpenAIEmbeddings` class implements the `EmbeddingBackend` protocol. Lazy import (only runs when instantiated).
- No `OpenAI` LLM class is shipped yet — the SDK is available as an extra mainly for embeddings. Adding `OpenAILLM` in `backends/llm.py` is a reasonable contribution.

## Why we picked it

Defensive — having a working alternative provider in the box makes the "backends are pluggable" claim concrete rather than aspirational.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| Azure OpenAI | Same SDK, different config. Use it if you're enterprise-locked; no separate package. |
| Direct HTTP | The SDK is light enough; no reason to roll our own. |

## How to swap it out

To use OpenAI embeddings instead of Voyage:

```python
from m3xa_core.backends.embeddings import OpenAIEmbeddings
pipeline = Pipeline(embeddings=OpenAIEmbeddings(), ...)
```

You will need to **re-embed the corpus** — vectors from different providers are not interchangeable.

## Links

- Homepage: <https://platform.openai.com>
- SDK on GitHub: <https://github.com/openai/openai-python>
- Last verified: 2026-05-19
