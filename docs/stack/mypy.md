# mypy

**Package:** `mypy`  •  **Version pin:** `>=1.10`  •  **Extras group:** `m3xa-core[dev]`  •  **Role:** Static type checker

## What it does

Type-checks `m3xa_core/`. Configured in `pyproject.toml` `[tool.mypy]`:

- `python_version = "3.11"`
- `strict = true`
- `warn_return_any = true`
- `warn_unused_configs = true`

Strict mode is feasible because the codebase is small and the public surface is hint-complete.

## Where it's used in m3xa-core

- `pyproject.toml` `[tool.mypy]` — config.
- `CONTRIBUTING.md` — `mypy m3xa_core/` listed as part of the pre-commit checklist.
- `m3xa_core/py.typed` marker is shipped (see `[tool.setuptools.package-data]`) so downstream consumers get types for free.

## Why we picked it

- The reference Python type checker. If we ship `py.typed`, our consumers' mypy needs to agree with ours.
- Strict mode catches actor-to-actor schema drift early.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `pyright` | Faster, similar coverage. Worth revisiting if Microsoft's CLI ergonomics improve. |
| `pytype` (Google) | Inference-heavy. Doesn't fit "strict mode is the floor." |

## How to swap it out

If a contributor prefers pyright locally, they can run it — strict-mypy output is generally a superset of strict-pyright errors. Keep mypy as the CI source of truth.

## Links

- Homepage: <https://mypy.readthedocs.io>
- GitHub: <https://github.com/python/mypy>
- Last verified: 2026-05-19
