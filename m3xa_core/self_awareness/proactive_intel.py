"""proactive_intel — five triggers that initiate output without a user query.

Triggers:
  1. Burst detection — single entity mentioned across many sources fast
  2. Counter-narrative — state-aligned source flipped tone vs analytical sources
  3. Calendar threshold — known event within N hours
  4. Market move — Polymarket / FX / rate move exceeds threshold
  5. Source silence — tier-1 source on tracked topic unusually quiet

Each trigger fires a *mini report* to the distribution layer. Cooldowns
per trigger prevent alert fatigue.
"""
from __future__ import annotations


def check_triggers() -> list[dict]:
    """Run all five trigger checks; return fired triggers. Skeleton."""
    raise NotImplementedError


def emit_mini_report(trigger: dict) -> str:
    """Produce the short, focused report for a fired trigger. Skeleton."""
    raise NotImplementedError
