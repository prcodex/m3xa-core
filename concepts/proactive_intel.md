---
name: proactive_intel
description: Five triggers that initiate output without a user query — burst, counter-narrative, calendar, market move, source silence
type: concept
applies_to: m3xa-core
status: stub
---

# Proactive intel

> The only self-awareness component that *initiates* output. Five triggers — each watches a different signal in `unified_feed`, the markets stream, and the source-health table; each emits a mini report when it fires.

Stub. Full essay covers each trigger:

1. **Burst detection** — single entity mentioned across N+ sources in M-minute window
2. **Counter-narrative** — state-aligned source flipped tone while analytical sources still on previous narrative
3. **Calendar threshold** — known scheduled event (central bank meeting, election, OPEC) within N hours
4. **Market move** — Polymarket / FX / rate move exceeds threshold
5. **Source silence** — tier-1 source on a tracked topic has been unusually quiet

Also: the *3-hour mini report* output format (shorter than intel_summary, focused on one trigger), and how proactive_intel avoids alert fatigue (cooldowns per trigger).
