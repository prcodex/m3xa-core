# feedparser

**Package:** `feedparser`  •  **Version pin:** `>=6.0`  •  **Role:** RSS + Atom parsing for the scraper templates

## What it does

Parses RSS 1.0, RSS 2.0, Atom 0.3, and Atom 1.0 feeds with a uniform output shape. Handles the long tail of malformed feeds in the wild without crashing.

## Where it's used in m3xa-core

- `m3xa_core/scrapers/rss_template.py` — the only consumer in the public templates.

## Why we picked it

- Standard for "just parse this feed, I don't care how malformed it is."
- Pure Python, no extra runtime dependencies.
- Stable API — code from 2015 still works.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `lxml` + hand rolling | Fights every malformed feed individually. Bad use of time. |
| `defusedxml` | Better for hostile XML; we're reading editorial feeds, not user uploads. |
| `atoma` | Cleaner API but loses on the long-tail compatibility. |

## How to swap it out

If you only consume a handful of well-formed feeds, swap to `defusedxml` and parse by hand. For the typical scraper case, `feedparser` is the right default.

## Links

- Homepage: <https://feedparser.readthedocs.io>
- GitHub: <https://github.com/kurtmckee/feedparser>
- Last verified: 2026-05-20
