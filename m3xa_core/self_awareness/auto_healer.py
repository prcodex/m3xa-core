"""auto_healer — remediates RED items with known fixes, without asking.

For health-check failures with a known remediation, the auto-healer
applies it. Examples:

- Crashed scraper -> restart
- LanceDB returned zero rows on recently-ingested data -> call .optimize()
- Stale process surviving systemd restart -> pkill + let systemd respawn
- Stale FeedCache -> invalidate

Never touches the Soul or the Mind. Blast radius bounded by what it
can do without asking.
"""
from __future__ import annotations

from collections.abc import Callable

# A remediation is a callable taking the health-item dict and returning
# True if the item was healed.
Remediation = Callable[[dict], bool]


def _restart_scraper(item: dict) -> bool:
    """Mark the scraper for systemd restart. The systemd unit re-spawns it.

    In production this would shell out to `systemctl restart`; the public
    repo logs the intent so the pattern is visible.
    """
    name = item.get("name", "?")
    print(f"[auto_healer] systemctl restart {name}.service")
    return True


def _optimize_lancedb(item: dict) -> bool:
    """Call .optimize() on the affected LanceDB table.

    Compacts fragments — a frequent cause of "zero rows returned" right
    after a large ingest.
    """
    table = item.get("table", "unified_feed")
    print(f"[auto_healer] lance optimize on table={table}")
    return True


def _pkill_zombie(item: dict) -> bool:
    """pkill any process matching `pattern`; systemd respawns it."""
    pattern = item.get("pattern", "")
    if not pattern:
        return False
    print(f"[auto_healer] pkill -f {pattern!r}")
    return True


def _invalidate_feedcache(item: dict) -> bool:
    """Mark the in-process FeedCache as stale; next read triggers reload."""
    key = item.get("key", "*")
    print(f"[auto_healer] feedcache invalidate key={key}")
    return True


REMEDIATIONS: dict[str, Remediation] = {
    "scraper_crashed": _restart_scraper,
    "lancedb_zero_rows": _optimize_lancedb,
    "zombie_process": _pkill_zombie,
    "stale_feedcache": _invalidate_feedcache,
}


def heal_if_known(health_item: dict) -> bool:
    """Apply a known remediation if available. Returns True if healed.

    Health-item shape:
        {
          "kind": "scraper_crashed" | ...,
          "name": "scraper_a" | "scraper_b",   # remediation-specific
          ...
        }

    Unknown kinds return False — the operator must look at it.
    """
    kind = health_item.get("kind")
    if not kind or kind not in REMEDIATIONS:
        return False
    try:
        return REMEDIATIONS[kind](health_item)
    except Exception as exc:  # noqa: BLE001
        print(f"[auto_healer] remediation {kind} failed: {exc}")
        return False
