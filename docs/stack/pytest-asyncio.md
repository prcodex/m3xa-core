# pytest-asyncio

**Package:** `pytest-asyncio`  •  **Version pin:** `>=0.23`  •  **Extras group:** `m3xa-core[dev]`  •  **Role:** Async test support

## What it does

Enables `async def test_*` functions. Today the pipeline is synchronous and no test actually uses it, but the dependency is in place so adding an async backend (e.g. `AsyncAnthropicLLM`) doesn't need a tooling change.

## Where it's used in m3xa-core

- `pyproject.toml` — `asyncio_mode = "auto"` so any `async def test_*` is automatically wrapped.
- No async tests exist yet.

## Why we picked it

The standard pytest plugin for async tests. Trivial to use; no point picking anything else.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `anyio` plugin | Worth it if we move to a multi-loop architecture. Not now. |

## How to swap it out

Remove from `[project.optional-dependencies].dev` if you're sure no test needs async. Easier to leave it.

## Links

- GitHub: <https://github.com/pytest-dev/pytest-asyncio>
- Last verified: 2026-05-19
