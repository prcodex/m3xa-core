"""conversation_learner — aggregates follow-up + intent stats across sessions.

Watches multi-turn sessions. When the user asks a follow-up, that's a
signal the first answer was incomplete. Aggregates:

- Follow-up rate per expertise — which expertises produce "but what about…"?
- Source quality per follow-up — when followed up, was the original light on the relevant tier?
- Intent shifts — does intent change between turns in predictable ways?

Output feeds into soul_amendment_engine when a pattern is loud enough.
"""
from __future__ import annotations


def record_turn(session_id: str, turn_data: dict) -> None:
    """Persist one conversation turn. Skeleton."""
    raise NotImplementedError


def aggregates_by_expertise(window_days: int = 30) -> dict:
    """Compute per-expertise stats over a window. Skeleton."""
    raise NotImplementedError
