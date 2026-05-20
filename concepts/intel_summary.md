---
name: intel_summary
description: The 8×/day briefing — analyst prompt, actor monitor, source tiering, attribution discipline
type: concept
applies_to: m3xa-core
status: stub
---

# Intel summary

> Every 2 hours, the system produces a brief: what happened, what markets did, what experts said. The architecture is small (one Haiku call) but the prompt design is the lesson — *strict attribution*, *actor monitoring* (Actor1, Actor2, …), *source tiering* baked into the rubric.

Stub. Full essay covers:

- The three sections: WHAT HAPPENED · WHAT MARKETS DID · EXPERT TAKES
- The strict-attribution rule: "ONLY attribute a claim to a named person if THAT EXACT source said it" — prevents hallucinated sourcing
- The actor monitor — six geopolitical actors (`Actor1` … `Actor6`) with mention counts + signal/noise classification
- The 2-hour window vs 3-hour window trade-off (less stale ↔ more signal)
- Guard clauses: <3 usable headlines → graceful error instead of garbage
- Token budget: ~3K input, ~800 output, ~$0.05 per run
