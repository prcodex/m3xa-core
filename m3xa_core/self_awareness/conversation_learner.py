"""conversation_learner — aggregates follow-up + intent stats across sessions.

Watches multi-turn sessions. When the user asks a follow-up, that's a
signal the first answer was incomplete. Aggregates:

- Follow-up rate per expertise — which expertises produce "but what about ..."?
- Source quality per follow-up — when followed up, was the original light on the relevant tier?
- Intent shifts — does intent change between turns in predictable ways?

Output feeds into soul_amendment_engine when a pattern is loud enough.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path.home() / ".m3xa" / "memory.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_turns (
    session_id   TEXT NOT NULL,
    turn_index   INTEGER NOT NULL,
    recorded_at  TEXT NOT NULL,
    query        TEXT NOT NULL,
    expertise    TEXT NOT NULL DEFAULT 'unknown',
    intent       TEXT NOT NULL DEFAULT 'question',
    n_docs       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, turn_index)
);
CREATE INDEX IF NOT EXISTS idx_turns_at ON conversation_turns(recorded_at);
"""


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def record_turn(session_id: str, turn_data: dict, *, db_path: Path | None = None) -> None:
    """Persist one conversation turn.

    `turn_data` shape: {turn_index, query, expertise, intent, n_docs}.
    Missing fields fall back to sensible defaults.
    """
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO conversation_turns "
            "(session_id, turn_index, recorded_at, query, expertise, intent, n_docs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                int(turn_data.get("turn_index", 0)),
                datetime.now(tz=timezone.utc).isoformat(),
                str(turn_data.get("query", "")),
                str(turn_data.get("expertise", "unknown")),
                str(turn_data.get("intent", "question")),
                int(turn_data.get("n_docs", 0)),
            ),
        )


def aggregates_by_expertise(window_days: int = 30, *, db_path: Path | None = None) -> dict:
    """Compute per-expertise stats over a window.

    Returns:
        {
          "macro_lens": {
            "turns": int,
            "sessions": int,
            "follow_up_rate": float,   # turns_after_first / sessions
            "avg_docs": float
          },
          ...
        }
    """
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=window_days)).isoformat()
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT expertise, session_id, turn_index, n_docs "
            "FROM conversation_turns WHERE recorded_at >= ?",
            (cutoff,),
        ).fetchall()

    by_exp: dict[str, dict] = {}
    for expertise, session_id, turn_index, n_docs in rows:
        slot = by_exp.setdefault(
            expertise,
            {"turns": 0, "sessions": set(), "follow_up_turns": 0, "docs_sum": 0},
        )
        slot["turns"] += 1
        slot["sessions"].add(session_id)
        if turn_index > 0:
            slot["follow_up_turns"] += 1
        slot["docs_sum"] += n_docs

    out: dict[str, dict] = {}
    for expertise, slot in by_exp.items():
        n_sessions = len(slot["sessions"]) or 1
        out[expertise] = {
            "turns": slot["turns"],
            "sessions": n_sessions,
            "follow_up_rate": round(slot["follow_up_turns"] / n_sessions, 3),
            "avg_docs": round(slot["docs_sum"] / max(1, slot["turns"]), 2),
        }
    return out


def export_aggregates_jsonl(path: Path, window_days: int = 30) -> None:
    """Dump aggregates to JSONL for downstream consumers."""
    agg = aggregates_by_expertise(window_days=window_days)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for expertise, stats in sorted(agg.items()):
            f.write(json.dumps({"expertise": expertise, **stats}) + "\n")
