"""log_manager — rotation + compaction + archival.

Boring but essential. Daily:
  - Rotate JSONL logs older than 7 days into .gz
  - Compact SQLite DBs (memory.db, golden_exchanges.db, brainstorm_sessions.db)
  - Archive >90-day logs to cold storage (S3-shaped; the repo ships local-disk only)

Without it, the other components' logs grow until they crowd everything else.
"""
from __future__ import annotations

import gzip
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_ROOTS = (
    Path.home() / ".m3xa" / "self_eval",
    Path.home() / ".m3xa" / "interaction_log",
)
DB_PATHS = (
    Path.home() / ".m3xa" / "memory.db",
    Path.home() / ".m3xa" / "golden_exchanges.db",
    Path.home() / ".m3xa" / "brainstorm_sessions.db",
)
COLD_ROOT = Path.home() / ".m3xa" / "cold_storage"


def _is_older_than(path: Path, days: int) -> bool:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return False
    return mtime < datetime.now(tz=timezone.utc) - timedelta(days=days)


def rotate_old_logs(days: int = 7, *, roots: tuple[Path, ...] | None = None) -> int:
    """Gzip JSONL logs older than `days`. Returns count rotated.

    Skips files already ending in `.gz`. Removes the original after a
    successful gzip — bounded blast radius (one file at a time).
    """
    targets = roots or LOG_ROOTS
    n = 0
    for root in targets:
        if not root.exists():
            continue
        for path in root.glob("*.jsonl"):
            if not _is_older_than(path, days):
                continue
            gz = path.with_suffix(path.suffix + ".gz")
            if gz.exists():
                continue
            with path.open("rb") as src, gzip.open(gz, "wb") as dst:
                shutil.copyfileobj(src, dst)
            path.unlink(missing_ok=True)
            n += 1
    return n


def compact_dbs(*, paths: tuple[Path, ...] | None = None) -> list[Path]:
    """Run VACUUM on each SQLite DB. Returns the list of compacted paths."""
    out: list[Path] = []
    for p in (paths or DB_PATHS):
        if not p.exists():
            continue
        try:
            with sqlite3.connect(p) as conn:
                conn.execute("VACUUM")
        except sqlite3.Error as exc:
            print(f"[log_manager] VACUUM {p.name} failed: {exc}")
            continue
        out.append(p)
    return out


def archive_old_logs(days: int = 90, *, roots: tuple[Path, ...] | None = None) -> int:
    """Move very-old gzipped logs to COLD_ROOT. Returns count archived."""
    targets = roots or LOG_ROOTS
    COLD_ROOT.mkdir(parents=True, exist_ok=True)
    n = 0
    for root in targets:
        if not root.exists():
            continue
        for path in root.glob("*.jsonl.gz"):
            if not _is_older_than(path, days):
                continue
            dest = COLD_ROOT / path.name
            shutil.move(str(path), dest)
            n += 1
    return n
