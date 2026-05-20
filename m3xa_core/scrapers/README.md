# Scraper templates

Six pattern templates demonstrating how raw web content lands in `unified_feed`. They are **starting points**, not live scrapers. Real auth, real selectors, real rate-limit handling go in your own private fork.

## What each scraper has to do

Every scraper, regardless of source type, has the same job:

1. **Fetch** the source (RSS, HTML, Substack API, YouTube transcript, IMAP mailbox, …)
2. **Identify** each item with a stable id (URL hash, message id, video id, …) — used for dedupe
3. **Extract** text + minimal metadata (title, author, published_at)
4. **Chunk** if the item is long (>~1500 chars typical); each chunk becomes one row
5. **Embed** the chunk using the project's embedding backend
6. **Write** to `unified_feed` with `has_vector=1.0` set
7. **Mark health** — write a heartbeat so the `health_caveats_writer` can detect outages

The templates show steps 1-7 with placeholders for source-specific logic.

## The six templates

| Template | Source shape | Notes |
|---|---|---|
| `substack_template.py` | Substack newsletters (paid or free) | Cloudflare-aware; use `curl` not `requests` for the paid ones |
| `rss_template.py` | Generic RSS / Atom feeds | Plain feedparser, works for most editorial sources |
| `twitter_template.py` | Twitter accounts via API or scraper | Treat each thread as one document; pin the author |
| `youtube_transcript_template.py` | YouTube channels | Use a transcript service (Supadata-shape); one row per episode |
| `email_template.py` | IMAP/POP3 mailboxes | For newsletters that only arrive by email |
| `web_template.py` | Generic web page fetcher | When the source has no feed; use Trafilatura for boilerplate-stripping |

## Common conventions

- **`source` column is an alias.** Use `Bank1`, `Expert1`, `Podcast1` from `docs/source_naming.md`. **Never** the real name, even in commit messages.
- **`domain` column partitions the corpus.** Common values: `macro`, `geo`, `ai`, `region`. See `concepts/domain_split_pattern.md`.
- **`has_vector` is a contract.** Set to `1.0` when the row has a populated `content_vector`. The retriever filters on `has_vector = 1.0` — vectorless rows are invisible to search.
- **One row per chunk.** A long article becomes N rows with the same `parent_id` but distinct `id`s.
- **Stable ids matter.** If you reprocess the same content with a different chunker, you'll dedupe properly only if `id` is deterministic (hash of URL + chunk index works).

## Anti-patterns

- **Don't** populate `content_vector` without setting `has_vector=1.0`. Caused multiple "scraper looks fine but bot doesn't see new docs" incidents.
- **Don't** use Python `requests` for Cloudflare-fronted sources (most paid Substacks). They 403 on TLS fingerprint. Shell out to `curl` instead.
- **Don't** silently swallow scraper exceptions. Catch them, mark the health entry RED, let `health_caveats_writer` produce a user-facing caveat.

## After you fill in a template

Run, in your private fork:

```bash
python -m my_private_scrapers.substack_runner --source Expert1
python tools/check_anonymization.py    # don't accidentally commit a real name
```

The check above is the one that travels back to the public m3xa-core repo when you contribute pattern improvements upstream.
