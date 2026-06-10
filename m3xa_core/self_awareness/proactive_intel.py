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

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_FILE = Path.home() / ".m3xa" / "proactive_state.json"


@dataclass
class Trigger:
    name: str
    cooldown_minutes: int
    check: Callable[[], dict | None]


@dataclass
class ProactiveState:
    """Tracks last-fired timestamps per trigger."""

    last_fired: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "ProactiveState":
        p = path or STATE_FILE
        if not p.exists():
            return cls()
        try:
            return cls(last_fired=json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        p = path or STATE_FILE
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.last_fired, indent=2), encoding="utf-8")

    def in_cooldown(self, name: str, cooldown_minutes: int) -> bool:
        last = self.last_fired.get(name)
        if not last:
            return False
        try:
            t = datetime.fromisoformat(last)
        except ValueError:
            return False
        return datetime.now(tz=timezone.utc) - t < timedelta(minutes=cooldown_minutes)

    def stamp(self, name: str) -> None:
        self.last_fired[name] = datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Default trigger implementations — stubs that real installations replace
# with concrete checks over their unified_feed + market backends.
# ---------------------------------------------------------------------------
def _default_burst() -> dict | None:
    """Real check: SELECT entity, COUNT(*) FROM unified_feed WHERE
    published_at > now()-30min GROUP BY entity HAVING COUNT(*) > 8."""
    return None


def _default_counter_narrative() -> dict | None:
    """Real check: cosine sim between StateN tone vector and ExpertN tone vector
    over the last 24h, fire when |delta| > 0.6 on a tracked topic."""
    return None


def _default_calendar() -> dict | None:
    """Real check: query the calendar table for events inside [now, now+4h]
    with `priority >= 'high'`."""
    return None


def _default_market_move() -> dict | None:
    """Real check: any tracked instrument whose 1h % change > 2 sigma of its
    trailing 30-day distribution."""
    return None


def _default_source_silence() -> dict | None:
    """Real check: Wire1, Bank1, Expert1 each have an expected daily cadence;
    fire when a tier-1 source is silent on a tracked topic > 6h."""
    return None


DEFAULT_TRIGGERS: list[Trigger] = [
    Trigger("burst", cooldown_minutes=45, check=_default_burst),
    Trigger("counter_narrative", cooldown_minutes=180, check=_default_counter_narrative),
    Trigger("calendar", cooldown_minutes=60, check=_default_calendar),
    Trigger("market_move", cooldown_minutes=30, check=_default_market_move),
    Trigger("source_silence", cooldown_minutes=360, check=_default_source_silence),
]


def check_triggers(*, triggers: list[Trigger] | None = None) -> list[dict]:
    """Run every trigger; return the dicts for those that fired.

    A fired trigger is stamped immediately so the next iteration of the
    same call doesn't re-fire it.
    """
    state = ProactiveState.load()
    fired: list[dict] = []
    for t in (triggers or DEFAULT_TRIGGERS):
        if state.in_cooldown(t.name, t.cooldown_minutes):
            continue
        try:
            result = t.check()
        except Exception as exc:  # noqa: BLE001
            print(f"[proactive_intel] {t.name} failed: {exc}")
            continue
        if result is None:
            continue
        result["trigger"] = t.name
        fired.append(result)
        state.stamp(t.name)
    state.save()
    return fired


def emit_mini_report(trigger: dict) -> str:
    """Produce the short, focused report for a fired trigger.

    Real installations route this to Telegram (@MainBot / @RegionalBot)
    or the wiki. The shape is `<header>\\n<body>\\n<footer>` so a single
    sender doesn't need to know about every trigger type.
    """
    header = f"## Mini report — {trigger.get('trigger', '?')}"
    body = trigger.get("summary", "(no summary)")
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{header}\n\n{body}\n\n_fired at {ts}_"
