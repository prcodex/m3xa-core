# httpx

**Package:** `httpx`  •  **Version pin:** `>=0.27.0`  •  **Role:** HTTP client for the scraper templates

## What it does

Modern HTTP client with async support and HTTP/2. The scraper templates use it for non-Cloudflare-fronted sources; for Cloudflare-fronted ones, they shell out to `curl` instead (see `LESSONS.md` and `concepts/feedcache_block_on_stale.md`).

## Where it's used in m3xa-core

- `m3xa_core/scrapers/rss_template.py`
- `m3xa_core/scrapers/web_template.py`
- `m3xa_core/scrapers/twitter_template.py` (when not using a vendor API)

## Why we picked it

- Sync + async in one API
- HTTP/2 by default — important for modern editorial sites
- Better default timeouts than `requests`

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `requests` | No HTTP/2; sync-only; older defaults. Still fine for one-off scripts. |
| `aiohttp` | Async-only; we want sync for the simple templates. |
| `curl` shell-out | Needed specifically for Cloudflare-fronted Substacks (TLS fingerprint). Documented in the scraper README. |

## How to swap it out

Each template owns its own HTTP client. Swap inside the template if your target needs different behavior.

## Links

- Homepage: <https://www.python-httpx.org>
- GitHub: <https://github.com/encode/httpx>
- Last verified: 2026-05-20
