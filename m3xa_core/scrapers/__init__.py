"""Scraper templates — patterns, not live integrations.

Each *_template.py demonstrates the shape of a scraper that feeds
unified_feed: where to read, how to chunk, what columns to populate,
how to handle has_vector + content_vector, how to dedupe on id.

The reader copies the template into their own private repo and fills
in the source-specific details (selectors, auth, rate limits).

See m3xa_core/scrapers/README.md for the convention.
"""
