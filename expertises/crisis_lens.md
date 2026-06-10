---
name: crisis_lens
description: Loads when the query is about a breaking event — market dislocation, geopolitical escalation, sovereign default, sudden policy shift — where speed and source-tier discipline matter more than depth
version: 0.1.0
type: expertise
applies_to: macro
trigger_keywords: [breaking, crisis, escalation, halt, suspension, default, emergency, intervention, gap, shock]
trigger_entities: []
tokens_estimate: 500
---

# Crisis lens

> The breaking-event lens. Loads when something just happened and the response must compress timeline, source tier, and what's already priced into a small set of high-signal sentences. Speed over completeness; honesty about what's still unknown.

## What this covers

- Market dislocations (intraday gaps, halts, FX peg moves, sovereign curve dislocations)
- Geopolitical escalation events (strikes, summit collapses, sanctions surprises)
- Sudden policy shifts (emergency rate moves, intervention, capital controls)
- Sovereign credit events (default, restructuring, ratings shock)

## What this does NOT cover

- Slow-moving themes that have been developing for weeks → use the relevant domain lens directly
- Post-event analysis once the dust has settled → re-route to the domain lens
- Predictive scenarios for events that haven't happened → use `macro_lens.md` or `geo_lens.md`

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire2, Wire3, Wire4** — **wires dominate**. The first 30 minutes of a crisis are wire-only.
2. **Expert1, Expert2, Expert4, Expert6** — independent expert commentary as it appears; pin to the relevant domain
3. **Bank1, Bank2** — bulge-bracket flash notes (slower but synthesized)
4. **State1, State2, State3** — state-aligned framing when the event has a geopolitical edge
5. **Macro1, Macro2** — boutique cross-asset for "what positioning was crowded"

The crisis lens deliberately down-weights long-form analyst commentary in the first window. Their value comes later; this lens is the first response.

## Analytical framing

- **Timeline first, interpretation second.** The first paragraph is "what happened, with timestamps." Interpretation comes after.
- **Source tier is the credibility signal.** A Wire1 headline is more reliable in minute 5 than a Substack take in minute 30. Cite tier explicitly when there's ambiguity.
- **Distinguish observed from inferred.** "Market is down 4%" is observed. "Because of policy shift X" is inferred. Mark inference explicitly: `(inferred, no source attribution yet)`.
- **What's priced, what's not.** A crisis response is incomplete without a one-line read of what the market already priced and what it didn't. Even rough — "rates curve steepened 8bp before the announcement vs. 30bp after" — is more useful than narrative without numbers.
- **Name the uncertainty.** What we don't know is part of the response. List the open questions explicitly so the reader knows what to watch.

## Output format

Short and compressed:

- **Timeline** — bullet list of timestamps + events, 3-6 lines
- **What's priced** — one line on observed market reaction
- **Reading** — one short paragraph, hedged
- **Open questions** — 2-4 bullets, what we don't yet know

Maximum 350 words. The crisis lens response is meant to be readable on a phone in 30 seconds.

## Failure modes captured

- **YYYY-MM-DD:** Crisis response over 600 words including paragraph-long Bank1 quotes. **Fix:** in crisis mode the compression rule overrides the consensus-framing rule; bank synthesis goes in a follow-up, not the first response.
- **YYYY-MM-DD:** Response asserted causality between two events 4 minutes apart without checking whether one preceded the other in observed flow. **Fix:** correlation in time is not causation; mark causal claims as `(inferred)` until corroborated.
