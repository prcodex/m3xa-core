# Typer

**Package:** `typer`  •  **Version pin:** `>=0.12.0`  •  **Role:** CLI framework for the `m3xabr` entry point

## What it does

Turns Python type hints into a Click-based CLI. The `m3xabr` console script (defined in `pyproject.toml` and implemented in `m3xa_core/cli.py`) is a Typer app. Provides `m3xabr query "..."`, `m3xabr classify "..."`, etc.

## Where it's used in m3xa-core

- `m3xa_core/cli.py` — `app = typer.Typer()` plus the command definitions.

## Why we picked it

- Type hints are already required everywhere else in the repo. Typer is the closest thing to "free CLI from hints."
- Bundled `rich` integration gives readable help text without extra config.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `click` directly | More boilerplate, same features. Typer wraps it. |
| `argparse` | Standard library, but more boilerplate and worse help output. Fine for a 2-flag script — overkill-shaped wrong for this. |
| `fire` | Magical in ways that hurt when something breaks. |

## How to swap it out

The CLI is a thin demo wrapper — most callers will drive `Pipeline(...)` directly from their own application code. If you want a different CLI shape, rewrite `m3xa_core/cli.py` and update the `[project.scripts]` entry in `pyproject.toml`.

## Links

- Homepage: <https://typer.tiangolo.com>
- GitHub: <https://github.com/tiangolo/typer>
- Last verified: 2026-05-19
