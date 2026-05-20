---
name: narrative_drift_detection
description: How the system flags shifts in the dominant framing of a topic — and why this matters more than sentiment
type: concept
applies_to: m3xa-core
status: stub
---

# Narrative drift detection

> Sentiment trackers tell you whether sources are "positive" or "negative." That's the wrong question. The right one: *has the framing of the topic itself shifted?* — what counts as the question changed.

Stub. Full essay covers:

- Why "framing" matters more than "sentiment" for analytical workflows
- Detection: cluster recent docs by latent framing, compare to last week's clusters, flag divergence
- The "both-sides" intersection: drift detected only when *both* analytical and state-aligned sources shift in the same direction
- Output: a short report ("topic X has reframed from Y to Z over the past N days, here are the pivot pieces")
- Anti-pattern: triggering on noise — small-corpus topics produce false drift signals
