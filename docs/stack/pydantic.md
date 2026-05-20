# Pydantic

**Package:** `pydantic`  •  **Version pin:** `>=2.5.0`  •  **Role:** Schema validation for actor I/O

## What it does

Runtime validation + serialization for the dataclasses that flow between actors (`ClassifierOutput`, `RoutingDecision`, `AgentContext`, `RetrievedDoc`, `SynthesizerInput`, `EvaluationResult`, `PipelineResult`). Catches shape drift between actors before it becomes a confusing stack trace three steps later.

## Where it's used in m3xa-core

- `m3xa_core/schemas.py` — every pipeline-edge type is a Pydantic v2 `BaseModel`.
- Indirectly everywhere: each actor accepts and returns these models.

## Why we picked it

- **v2 speed.** Validation in the hot path (the retriever can produce dozens of `RetrievedDoc`s) needs to be fast.
- **JSON in/out.** The router's Haiku response is parsed into `RoutingDecision` with `model_validate_json()` — same contract on both sides.
- **Familiar.** Most Python LLM tooling has standardized on Pydantic. Don't introduce a new validation library when this is what readers already know.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `dataclasses` + manual checks | Loses JSON parsing, loses Haiku-output validation in one line. |
| `attrs` | Fine library, but Pydantic is the de-facto standard in this ecosystem. |
| `msgspec` | Faster, but small win at our scale and less familiar. |

## How to swap it out

You'd be touching the shape of the contract between actors. Probably not what you want — but if you must:

1. Replace each `BaseModel` in `schemas.py` with your alternative.
2. Update the router's JSON-parsing call (`m3xa_core/actors/router.py`).
3. Re-run `pytest tests/`.

## Links

- Homepage: <https://docs.pydantic.dev>
- GitHub: <https://github.com/pydantic/pydantic>
- Last verified: 2026-05-19
