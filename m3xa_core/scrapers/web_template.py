"""Generic web-page scraper template.

For sources without a feed. Periodically poll a known index/archive
page, diff against last seen, fetch + extract new items. Use Trafilatura
for boilerplate-stripping.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

SOURCE_ALIAS = "ThinkTank1"  # see docs/source_naming.md
INDEX_URL = "https://example.org/research"  # placeholder
DOMAIN = "geo"


def fetch(url: str) -> str:
    """Plain HTTP fetch with a polite User-Agent. Skeleton."""
    raise NotImplementedError


def discover_new_urls(index_html: str, *, seen_ids: set[str]) -> list[str]:
    """Parse the index page; return URLs whose hash isn't in seen_ids."""
    raise NotImplementedError


def extract(page_html: str) -> dict[str, Any]:
    """Trafilatura.extract → {title, author, published_at, body_text}. Skeleton."""
    raise NotImplementedError


def make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def run(
    *,
    embeddings: Any,
    vector_db: Any,
    seen_ids: set[str] | None = None,
    table_name: str = "unified_feed",
) -> int:
    seen_ids = seen_ids or set()
    rows_written = 0
    index_html = fetch(INDEX_URL)
    for url in discover_new_urls(index_html, seen_ids=seen_ids):
        item = extract(fetch(url))
        row_id = make_id(url)
        vector = embeddings.embed(item["body_text"])
        row = {
            "id": row_id,
            "text": item["body_text"],
            "source": SOURCE_ALIAS,
            "published_at": item.get("published_at") or datetime.now(timezone.utc),
            "domain": DOMAIN,
            "content_vector": vector,
            "has_vector": 1.0,
        }
        # vector_db.add_row(table_name, row)
        rows_written += 1
    return rows_written
