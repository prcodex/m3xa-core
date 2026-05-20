"""health_caveats_writer — temporary "the X scraper is degraded" warnings injected into RAG.

Writes short markdown caveats with a 6-hour TTL. The retriever reads
active caveats and prepends them to the synthesizer context. Why 6 hours:
long enough that the agent stays honest about the gap; short enough that
yesterday's broken scraper doesn't poison today's response.

Storage: .m3xa/health/caveats/<id>.md with frontmatter
{created_at, expires_at, topic, severity}.
"""
from __future__ import annotations


def write_caveat(*, topic: str, message: str, ttl_hours: int = 6) -> None:
    """Create a new caveat. Skeleton."""
    raise NotImplementedError


def active_caveats(*, topic: str | None = None) -> list[str]:
    """Return non-expired caveats, optionally filtered by topic. Skeleton."""
    raise NotImplementedError
