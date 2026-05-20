"""Body — runtime introspection of the infrastructure spec (BODY.md)."""
from __future__ import annotations

from pathlib import Path


def read_invariants(repo_root: Path) -> str:
    """Read the hand-written invariants section from BODY.md.

    Used by Actor 8 (future) to verify the live system matches the spec.
    Skeleton.
    """
    raise NotImplementedError
