"""RSS / Atom feed scraper template.

The simplest scraper shape — feedparser does most of the work. Use for
editorial outlets that publish full feeds.

For Cloudflare-fronted sources, see substack_template.py.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

SOURCE_ALIAS = "Wire1"  # see docs/source_naming.md
FEED_URL = "https://example.com/rss"  # placeholder
DOMAIN = "macro"


def fetch_feed(url: str) -> Any:
    """Parse an RSS/Atom feed.

    Skeleton — use feedparser.parse(url) in your private fork.
    """
    raise NotImplementedError


def extract_item(entry: Any) -> dict[str, Any]:
    """Pull a single feed item into our shape.

    Returns {title, link, published_at, body_text}.

    Most feeds include description/summary; some require fetching the
    link target for full text. Use Trafilatura on the linked page for
    the boilerplate-strip.
    """
    raise NotImplementedError


def make_id(link: str) -> str:
    """Stable id from the canonical link."""
    return hashlib.sha256(link.encode()).hexdigest()[:32]


def run(*, embeddings: Any, vector_db: Any, table_name: str = "unified_feed") -> int:
    """Fetch → for each entry → extract → embed → write. Returns rows written."""
    feed = fetch_feed(FEED_URL)
    rows_written = 0
    for entry in feed.entries:
        item = extract_item(entry)
        row_id = make_id(item["link"])
        # dedupe check skeleton
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
