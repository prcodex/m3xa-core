# Rich

**Package:** `rich`  •  **Version pin:** `>=13.0`  •  **Role:** Terminal output (formatted tables, syntax highlighting, progress)

## What it does

Pretty-prints pipeline results in the demo CLI — formatted markdown for the synthesizer output, colored tables for retrieved docs, syntax-highlighted JSON for the router decision. Strictly a developer-experience layer.

## Where it's used in m3xa-core

- `m3xa_core/cli.py` — `Console`, `Table`, `Markdown` for the demo commands.

## Why we picked it

- Bundled with Typer's help output anyway.
- Standard for "make a Python CLI look reasonable."

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| Plain `print` | Pipeline output (markdown blocks, JSON, tables) is unreadable as a stream of ANSI-less text. |
| `textual` | Full TUI framework. Way more than we need. |

## How to swap it out

Optional dependency in spirit — replace the Rich-using lines in `cli.py` with plain prints if you're piping output into another tool that doesn't want ANSI codes. The core pipeline doesn't import it.

## Links

- Homepage: <https://rich.readthedocs.io>
- GitHub: <https://github.com/Textualize/rich>
- Last verified: 2026-05-19
