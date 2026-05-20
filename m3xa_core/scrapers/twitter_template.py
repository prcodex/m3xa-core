"""Twitter scraper template — accounts as sources.

Treat each thread (root tweet + reply chain by the same author) as one
document. Pin the author alias from docs/source_naming.md. For
translation use cases (e.g., Arabic-language accounts), see the
translate-before-embed pattern in the docstring.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

ACCOUNT_ALIAS = "Expert2"  # see docs/source_naming.md
DOMAIN = "geo"
TRANSLATE_FROM_LANG = None  # set to e.g. "ar" if the account posts non-English


def fetch_recent_threads(account: str) -> list[dict[str, Any]]:
    """Return recent threads for an account.

    Skeleton — your private fork picks API vs scraper-based access.
    """
    raise NotImplementedError


def translate_if_needed(text: str, *, llm: Any) -> str:
    """Optional pre-embedding translation step.

    Voyage handles multilingual reasonably; translate only when the
    downstream synthesis prompt is English-only.
    """
    if TRANSLATE_FROM_LANG is None:
        return text
    raise NotImplementedError


def make_id(thread_root_id: str) -> str:
    return hashlib.sha256(f"tw::{thread_root_id}".encode()).hexdigest()[:32]


def run(
    *,
    embeddings: Any,
    vector_db: Any,
    llm: Any | None = None,
    table_name: str = "unified_feed",
) -> int:
    rows_written = 0
    for thread in fetch_recent_threads(ACCOUNT_ALIAS):
        row_id = make_id(thread["root_id"])
        text = " ".join(t["text"] for t in thread["tweets"])
        if TRANSLATE_FROM_LANG and llm is not None:
            text = translate_if_needed(text, llm=llm)
        vector = embeddings.embed(text)
        row = {
            "id": row_id,
            "text": text,
            "source": ACCOUNT_ALIAS,
            "published_at": datetime.fromisoformat(thread["created_at"]),
            "domain": DOMAIN,
            "content_vector": vector,
            "has_vector": 1.0,
        }
        # vector_db.add_row(table_name, row)
        rows_written += 1
    return rows_written
