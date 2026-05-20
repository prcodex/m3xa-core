"""auto_healer — remediates RED items with known fixes, without asking.

For health-check failures with a known remediation, the auto-healer
applies it. Examples:

- Crashed scraper → restart
- LanceDB returned zero rows on recently-ingested data → call .optimize()
- Stale process surviving systemd restart → pkill + let systemd respawn
- Stale FeedCache → invalidate

Never touches the Soul or the Mind. Blast radius bounded by what it
can do without asking.
"""
from __future__ import annotations


def heal_if_known(health_item: dict) -> bool:
    """Apply a known remediation if available. Returns True if healed.

    Skeleton.
    """
    raise NotImplementedError
