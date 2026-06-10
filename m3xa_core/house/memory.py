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

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation (
    session_id   TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,
    user_text    TEXT NOT NULL,
    response     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_session_at
    ON conversation(session_id, recorded_at);

CREATE TABLE IF NOT EXISTS golden_exchanges (
    id           TEXT PRIMARY KEY,
    recorded_at  TEXT NOT NULL,
    topic        TEXT NOT NULL,
    lesson_type  TEXT NOT NULL,
    body         TEXT NOT NULL,
    quality      REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_golden_topic ON golden_exchanges(topic);

CREATE TABLE IF NOT EXISTS brainstorm_session (
    session_id   TEXT PRIMARY KEY,
    updated_at   TEXT NOT NULL,
    state        TEXT NOT NULL
);
"""


class Memory:
    """SQLite-backed session memory.

    The class is opened lazily on first method call so importing the
    module is side-effect-free. Each method opens its own short-lived
    connection — SQLite is fast enough that pooling adds no value.
    """

    def __init__(self, db_path: Path | str = "~/.m3xa/memory.db") -> None:
        self.db_path = Path(str(db_path)).expanduser()
        self._opened = False

    def open(self) -> None:
        """Create the DB + schema if it doesn't exist. Idempotent."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
        self._opened = True

    def _conn(self) -> sqlite3.Connection:
        if not self._opened:
            self.open()
        return sqlite3.connect(self.db_path)

    # --- conversation history -----------------------------------------
    def record_turn(self, session_id: str, user: str, response: str) -> None:
        """Append one turn to the session."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversation (session_id, recorded_at, user_text, response) "
                "VALUES (?, ?, ?, ?)",
                (session_id, datetime.now(tz=timezone.utc).isoformat(), user, response),
            )

    def history(self, session_id: str, *, ttl_minutes: int = 30) -> list[dict]:
        """Return turns within the TTL window, oldest first."""
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(minutes=ttl_minutes)
        ).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT recorded_at, user_text, response FROM conversation "
                "WHERE session_id = ? AND recorded_at >= ? ORDER BY recorded_at ASC",
                (session_id, cutoff),
            ).fetchall()
        return [
            {"recorded_at": ts, "user": u, "response": r}
            for ts, u, r in rows
        ]

    # --- golden exchanges ---------------------------------------------
    def add_golden(
        self,
        *,
        id: str,
        topic: str,
        lesson_type: str,
        body: str,
        quality: float = 0.0,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO golden_exchanges "
                "(id, recorded_at, topic, lesson_type, body, quality) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    id,
                    datetime.now(tz=timezone.utc).isoformat(),
                    topic,
                    lesson_type,
                    body,
                    float(quality),
                ),
            )

    def golden_for_topic(self, topic: str, *, limit: int = 5) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, recorded_at, lesson_type, body, quality "
                "FROM golden_exchanges WHERE topic = ? "
                "ORDER BY quality DESC, recorded_at DESC LIMIT ?",
                (topic, limit),
            ).fetchall()
        return [
            {"id": i, "recorded_at": ts, "lesson_type": lt, "body": b, "quality": q}
            for i, ts, lt, b, q in rows
        ]
