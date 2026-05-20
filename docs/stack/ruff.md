# Ruff

**Package:** `ruff`  •  **Version pin:** `>=0.5`  •  **Extras group:** `m3xa-core[dev]`  •  **Role:** Linter + formatter

## What it does

Lints and formats the codebase. Replaces flake8 + isort + (most of) Black. Configured in `pyproject.toml` `[tool.ruff]`:

- `line-length = 100`
- `target-version = "py311"`
- `select = ["E", "F", "I", "N", "W", "UP", "B", "RUF"]`
- `ignore = ["E501"]` (we run long-line lines through `RUF` rather than `E`)

## Where it's used in m3xa-core

- `pyproject.toml` `[tool.ruff]` — config.
- `CONTRIBUTING.md` — `ruff check m3xa_core/ tests/` listed as part of the pre-commit checklist.

## Why we picked it

- 10-100× faster than the flake8-stack equivalents.
- One tool replaces three; one config block.
- Active development, sensible defaults.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| flake8 + isort + black | Three tools, three configs, much slower. No upside vs Ruff today. |
| pylint | Stricter but slower; the rule set we use overlaps with Ruff's. |

## How to swap it out

Don't. Lint output stays compatible across versions and the speed is hard to beat.

## Links

- Homepage: <https://docs.astral.sh/ruff/>
- GitHub: <https://github.com/astral-sh/ruff>
- Last verified: 2026-05-19
