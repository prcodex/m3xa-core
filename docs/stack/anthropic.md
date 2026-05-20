# Anthropic

**Package:** `anthropic`  •  **Version pin:** `>=0.40.0`  •  **Role:** LLM provider (Claude Sonnet for synthesis, Claude Haiku for classifier/router/evaluator)

## What it does

Official Python SDK for Anthropic's Messages API. m3xa-core uses it for every LLM call in the pipeline: one Haiku call each at the classifier, router, and evaluator stages, and one Sonnet call at the synthesizer.

## Where it's used in m3xa-core

- `m3xa_core/backends/llm.py` — the only place where `from anthropic import Anthropic` appears. Wrapped in `AnthropicLLM`, which implements the `LLMBackend` protocol.
- `m3xa_core/cli.py` — reads `ANTHROPIC_API_KEY` from the environment and instantiates `AnthropicLLM` for the demo CLI.

No other module imports the SDK. That isolation is intentional (see "How to swap it out" below).

## Why we picked it

- **Sonnet for quality.** The synthesizer is the user-visible output; Brazilian-Portuguese-aware long-form reasoning is where Sonnet earns its cost.
- **Haiku for cheap structured output.** Classifier + router + evaluator are bounded, JSON-shaped tasks. Haiku is ~10× cheaper and fast enough that we don't batch.
- **Stable SDK.** The Messages API contract has been steady. The `messages.create(...)` call shape in `backends/llm.py` has not needed migration since the repo's first commit.
- **First-class system prompt.** The assembler concatenates expertise files into the system prompt; Anthropic's API treats `system` as a top-level field rather than an in-message hack.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| OpenAI (gpt-4o, o-series) | Equivalent quality but no compelling reason to switch from the model we've tuned the prompts against. Available as an extra (`m3xa-core[openai]`) for callers who want it. |
| Local LLM (Ollama, vLLM) | The synthesizer needs strong Portuguese — most open-weights models lose quality there. Worth revisiting once a Portuguese-tuned 70B+ model is widely available. |
| Bedrock-hosted Claude | Same models, more deploy complexity. Skip unless an enterprise caller needs it; the protocol abstraction in `backends/llm.py` makes the swap trivial. |

## How to swap it out

The contract is the `LLMBackend` Protocol in `m3xa_core/backends/llm.py`:

```python
class LLMBackend(Protocol):
    def complete(self, *, model: str, system: str, user: str,
                 max_tokens: int = 4096, temperature: float = 0.0) -> str: ...
```

Steps:

1. Add a class in `backends/llm.py` (or a new file) that implements `complete`.
2. Construct it in your entry point and pass it to `Pipeline(llm=your_backend, ...)`.
3. Update the model strings — Sonnet/Haiku names won't match your provider. Search for `model=` in `m3xa_core/actors/` to find call sites.

The rest of the codebase never sees the vendor SDK, so no other changes are needed.

## Links

- Homepage: <https://www.anthropic.com/api>
- SDK on GitHub: <https://github.com/anthropics/anthropic-sdk-python>
- Messages API reference: <https://docs.anthropic.com/en/api/messages>
- Last verified: 2026-05-19
