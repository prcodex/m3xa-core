"""YouTube transcript scraper template.

For long-form podcast/interview YouTube channels (Podcast4, Podcast5,
etc. — see docs/source_naming.md). Strategy: one row per episode (NOT
per chunk), with the full transcript or a cleaned summary as `text`.

Why one row per episode:
  - The retrieval is "which episode talks about X?", not "which timestamp"
  - Chunking destroys cross-references between the host and the guest
  - The vector benefits from the full context

The transcript itself comes from a third-party service (Supadata-shape;
free YouTube transcripts work for some channels). The template assumes
the service is called and a transcript string returned.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

CHANNEL_ALIAS = "Podcast4"  # see docs/source_naming.md
CHANNEL_URL = "https://www.youtube.com/@example"  # placeholder
DOMAIN = "geo"


def list_recent_episodes(channel_url: str) -> list[dict[str, Any]]:
    """Return {video_id, title, published_at, guest} for recent uploads.

    Skeleton — use the channel's RSS feed
    (https://www.youtube.com/feeds/videos.xml?channel_id=…) in your fork.
    """
    raise NotImplementedError


def fetch_transcript(video_id: str) -> str:
    """Get the raw transcript text for a YouTube video.

    Skeleton — call your transcript service in your private fork.
    """
    raise NotImplementedError


def clean_with_llm(transcript: str, *, llm: Any) -> dict[str, Any]:
    """Use Haiku to clean + summarize + extract guest from the raw transcript.

    Returns {clean_text, summary, guest_name, key_topics}.

    Why: raw YouTube transcripts are noisy ("um", repeated phrases,
    music tags). The clean text vectorizes much better.
    """
    raise NotImplementedError


def make_id(video_id: str) -> str:
    return hashlib.sha256(f"yt::{video_id}".encode()).hexdigest()[:32]


def run(
    *,
    embeddings: Any,
    vector_db: Any,
    llm: Any,
    table_name: str = "unified_feed",
) -> int:
    """For each new episode → transcribe → clean → embed → write."""
    rows_written = 0
    for ep in list_recent_episodes(CHANNEL_URL):
        row_id = make_id(ep["video_id"])
        # dedupe check skeleton
        transcript = fetch_transcript(ep["video_id"])
        cleaned = clean_with_llm(transcript, llm=llm)

        # Embed the focused context, not the raw 60K-char transcript —
        # a focused embedding ranks much higher in retrieval.
        focus_text = (
            f"{ep['title']}\n\n"
            f"Guest: {cleaned['guest_name']}\n"
            f"Topics: {', '.join(cleaned['key_topics'])}\n\n"
            f"Summary: {cleaned['summary']}\n\n"
            f"{cleaned['clean_text'][:1500]}"
        )
        vector = embeddings.embed(focus_text)

        row = {
            "id": row_id,
            "text": cleaned["clean_text"],
            "source": CHANNEL_ALIAS,
            "published_at": datetime.fromisoformat(ep["published_at"]),
            "domain": DOMAIN,
            "content_vector": vector,
            "has_vector": 1.0,
            "metadata": {
                "guest": cleaned["guest_name"],
                "topics": cleaned["key_topics"],
                "video_id": ep["video_id"],
            },
        }
        # vector_db.add_row(table_name, row)
        rows_written += 1
    return rows_written
