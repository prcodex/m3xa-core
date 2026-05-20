"""Memory — short-term session state + golden exchanges + health caveats.

Backed by a small SQLite DB (~/.m3xa/memory.db by default).

Holds:
  - Conversation history (TTL ~30 min)
  - Golden exchanges (decay over 30 days, never auto-deleted)
  - Health caveats (TTL 6h, see health_caveats_writer)
  - Brainstorm session state (persisted across reboots)

Why SQLite and not LanceDB: Memory is small, typed, frequently mutated,
not retrieval-search-shaped. LanceDB is for the document corpus.
"""
from __future__ import annotations

from pathlib import Path


class Memory:
    def __init__(self, db_path: Path | str = "~/.m3xa/memory.db") -> None:
        self.db_path = Path(str(db_path)).expanduser()

    def open(self) -> None:
        """Open / create the DB. Skeleton."""
        raise NotImplementedError

    def record_turn(self, session_id: str, user: str, response: str) -> None:
        """Skeleton."""
        raise NotImplementedError

    def history(self, session_id: str, *, ttl_minutes: int = 30) -> list[dict]:
        """Skeleton."""
        raise NotImplementedError
