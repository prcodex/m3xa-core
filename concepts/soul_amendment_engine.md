---
name: soul_amendment_engine
description: How the agent proposes edits to its own Soul — patterns → drafts → human approval
type: concept
applies_to: m3xa-core
status: stub
---

# Soul amendment engine

> The most consequential of the nine self-awareness components. Reads `self_evaluator`'s structural-failure log over a moving window; when a pattern repeats (same expertise, same error class, ≥3 hits), it drafts a proposed amendment to the soul module that owns that expertise. **Never auto-applied.** A human types `#approve` or `#reject`.

Stub. Full essay covers:

- The detection window — moving N-response window per expertise, with cooldowns to avoid amendment spam
- The draft format: diagnosis + suggested patch + triggering responses
- The `#approve` / `#reject` gate (and why direct human edits to the soul module are also fine — the engine notices and stops proposing)
- Why this is the *one* component that never runs autonomously
- The blast-radius argument: Soul edits change every future response; that's a different category of risk from Memory edits
