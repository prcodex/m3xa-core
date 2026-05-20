# python-dateutil

**Package:** `python-dateutil`  •  **Version pin:** `>=2.8`  •  **Role:** Robust date parsing for heterogeneous source feeds

## What it does

Parses `published_at` timestamps from corpus rows where the format varies by source. The standard library's `fromisoformat` is strict; real-world feeds emit RFC 2822, RFC 3339, and ad-hoc ISO variants in the same table.

## Where it's used in m3xa-core

- `m3xa_core/actors/retriever.py` — when sorting/filtering retrieved docs by recency.
- `m3xa_core/actors/synthesizer.py` — when formatting timestamps for the system prompt.

## Why we picked it

The "just parse the date, I don't care how" library. Adds dependency weight worth the headache it removes.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `datetime.fromisoformat` only | Fails on any feed that emits non-strict ISO (most of them). |
| `pendulum` / `arrow` | Heavier, more API. We only need parsing. |

## How to swap it out

If your corpus has guaranteed-strict ISO timestamps, drop this and use stdlib. Otherwise leave it.

## Links

- Homepage: <https://dateutil.readthedocs.io>
- GitHub: <https://github.com/dateutil/dateutil>
- Last verified: 2026-05-19
