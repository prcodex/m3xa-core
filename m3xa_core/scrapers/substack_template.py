"""Substack scraper template — paid + free newsletters.

Pattern, not a live scraper. Replace `SOURCE_ALIAS` and the URL with your
actual target (in your private fork — never commit a real source name).

Key lessons baked in:
  - Use curl, not Python requests, for Cloudflare-fronted paid Substacks
  - Strip boilerplate before vectorizing — paid newsletters have long
    headers/footers that dilute the vector
  - Idempotent on stable URL — re-running on the same content is a no-op
  - Set has_vector=1.0 alongside content_vector (see LESSONS.md)
"""
from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime
from typing import Any

# Anonymized alias from docs/source_naming.md.
SOURCE_ALIAS = "Expert1"
SOURCE_BASE_URL = "https://example.substack.com"  # placeholder

# Embeddings + vector DB backends are passed in — the template doesn't
# instantiate them. See m3xa_core/backends/.


def fetch_with_curl(url: str, *, cookie_jar: str | None = None) -> str:
    """Cloudflare-aware fetch. Python requests 403s; curl works.

    Pass the cookie jar path for paid Substacks. None for free ones.
    """
    cmd = ["curl", "-sL"]
    if cookie_jar:
        cmd += ["-b", cookie_jar]
    cmd.append(url)
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def discover_post_urls(html: str) -> list[str]:
    """Parse the archive page and return post URLs.

    Skeleton — fill in with BeautifulSoup or regex.
    """
    raise NotImplementedError


def extract_post(html: str) -> dict[str, Any]:
    """Parse a single post page.

    Returns {title, author, published_at, body_text}.

    Skeleton — fill in with Trafilatura or hand-rolled extraction.
    """
    raise NotImplementedError


def chunk(text: str, max_chars: int = 1500) -> list[str]:
    """Split long posts into chunks. Default 1500 chars, on paragraph boundaries."""
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) > max_chars and current:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current.strip():
        chunks.append(current.strip())
    return chunks


def make_id(url: str, chunk_idx: int) -> str:
    """Stable id — deterministic on URL + chunk index."""
    return hashlib.sha256(f"{url}::{chunk_idx}".encode()).hexdigest()[:32]


def run(*, embeddings: Any, vector_db: Any, table_name: str = "unified_feed") -> int:
    """Fetch → extract → chunk → embed → write.

    Returns the number of new rows written. Idempotent: stable ids mean
    re-runs are no-ops.

    Skeleton — wire up your private discover/fetch implementation.
    """
    rows_written = 0
    archive_html = fetch_with_curl(f"{SOURCE_BASE_URL}/archive")
    for post_url in discover_post_urls(archive_html):
        post_html = fetch_with_curl(post_url)
        post = extract_post(post_html)
        for idx, chunk_text in enumerate(chunk(post["body_text"])):
            row_id = make_id(post_url, idx)
            # if vector_db.has_id(row_id): continue   # dedupe — skeleton
            vector = embeddings.embed(chunk_text)
            row = {
                "id": row_id,
                "text": chunk_text,
                "source": SOURCE_ALIAS,
                "published_at": datetime.fromisoformat(post["published_at"]),
                "domain": "macro",
                "content_vector": vector,
                "has_vector": 1.0,  # NEVER omit this — see LESSONS.md
            }
            # vector_db.add_row(table_name, row)   # skeleton
            rows_written += 1
    return rows_written
