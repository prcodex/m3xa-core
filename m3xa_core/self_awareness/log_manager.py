"""log_manager — rotation + compaction + archival.

Boring but essential. Daily:
  - Rotate JSONL logs older than 7 days into .gz
  - Compact SQLite DBs (memory.db, golden_exchanges.db, brainstorm_sessions.db)
  - Archive >90-day logs to cold storage (S3-shaped; the repo ships local-disk only)

Without it, the other components' logs grow until they crowd everything else.
"""
from __future__ import annotations


def rotate_old_logs(days: int = 7) -> int:
    """Gzip JSONL logs older than `days`. Returns count rotated. Skeleton."""
    raise NotImplementedError


def compact_dbs() -> None:
    """Run VACUUM on each SQLite DB. Skeleton."""
    raise NotImplementedError
