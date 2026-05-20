"""Email newsletter scraper template.

For newsletters that only arrive by email (paid daily wrap-ups, expert
mailing lists). Connect via IMAP, filter by sender, extract HTML body,
strip tracking pixels and unsubscribe footers.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

SOURCE_ALIAS = "Macro1"  # see docs/source_naming.md
SENDER_FILTER = "newsletter@example.com"  # placeholder
DOMAIN = "macro"


def fetch_new_messages(imap_host: str, account: str, password: str) -> list[dict[str, Any]]:
    """IMAP fetch. Skeleton — uses imaplib in your private fork."""
    raise NotImplementedError


def extract_body(html: str) -> str:
    """Strip footers, tracking pixels, image alt-text bloat. Return clean text."""
    raise NotImplementedError


def make_id(message_id: str) -> str:
    return hashlib.sha256(f"mail::{message_id}".encode()).hexdigest()[:32]


def run(
    *,
    embeddings: Any,
    vector_db: Any,
    imap_host: str,
    account: str,
    password: str,
    table_name: str = "unified_feed",
) -> int:
    rows_written = 0
    for msg in fetch_new_messages(imap_host, account, password):
        if SENDER_FILTER not in msg["from"]:
            continue
        text = extract_body(msg["html_body"])
        row_id = make_id(msg["message_id"])
        vector = embeddings.embed(text)
        row = {
            "id": row_id,
            "text": text,
            "source": SOURCE_ALIAS,
            "published_at": datetime.fromisoformat(msg["received_at"]),
            "domain": DOMAIN,
            "content_vector": vector,
            "has_vector": 1.0,
        }
        # vector_db.add_row(table_name, row)
        rows_written += 1
    return rows_written
