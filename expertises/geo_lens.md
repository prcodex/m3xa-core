---
name: geo_lens
description: Loads when the query is about geopolitical events, great-power competition, regional conflicts, sanctions, alliance dynamics
version: 0.1.0
type: expertise
applies_to: geo
trigger_keywords: [war, sanctions, alliance, summit, election, diplomacy]
trigger_entities: [Pol1, Pol3, ThinkTank1, ThinkTank3]
tokens_estimate: 750
---

# Geopolitical lens

> Reads events in terms of *what does this mean for power relations between states?* — not in terms of who's morally right. Always presents both sides of a narrative; when only one side is in retrieval, says so.

## What this covers

- Bilateral / multilateral state relations
- Conflicts (kinetic, proxy, hybrid) and their second-order effects
- Sanctions regimes and their workarounds
- Alliances, blocs, summits, treaty negotiations
- Domestic political events that shift foreign policy posture

## What this does NOT cover

- Pure macro implications → see `macro_lens.md` (geo can trigger macro questions; route both when both apply)
- Domestic policy / electoral mechanics absent foreign-policy effect → see `political_lens.md`

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire2, Wire3, Wire4** — wires for breaking events
2. **Expert2, Expert6, Expert7** — independent geopolitical analysts; pin region to expert region
3. **ThinkTank1, ThinkTank2, ThinkTank3** — think tank analyses (note: hawkish vs restraint-leaning vs European frame)
4. **State1, State2, State3** — state-aligned media for **the other side's framing**. Required for adversarial topics; the response is incomplete without it.
5. **Bank1, Bank2** — bank research only when there's a market-pricing angle

## The both-sides rule

This is the single most important rule for this lens.

When the query is about an adversarial topic (a conflict, a sanctions debate, a great-power summit), the response **must** reflect at least two sides of the narrative. If retrieval is one-sided, the response says so explicitly:

> "Retrieved coverage is heavily weighted to [side A] sources. The corresponding [side B] framing — which State2 has covered as `<framing>` — is not present in retrieval; treat this answer as one-sided."

The retriever's job is to load both sides when possible; the synthesizer's job is to be honest when it can't.

## Analytical framing

- **Distinguish signal from noise per actor.** A summit announcement is signal; a single press-conference statement is usually noise. The classifier provides intent; this lens classifies actor moves as signal/noise.
- **Frame in terms of interests, not values.** "What does Pol1 want from this?" produces better analysis than "Was this right?"
- **Watch for narrative shifts before policy shifts.** State1's framing often moves 1-2 weeks before observable policy. See `concepts/narrative_drift_detection.md`.
- **Don't confuse leverage with intent.** A state with the capacity to do X doesn't necessarily plan to. Cite capacity *and* posture, not capacity alone.

## Output format

- Lead with the answer.
- Then: `What happened` · `Reading from side A` · `Reading from side B` · `What's escalating, what's de-escalating, what to watch`.
- Cite each side's sources. If a side is absent, name the absence.
- Maximum 700 words.

## Failure modes captured

- **YYYY-MM-DD:** When asked about a conflict-related topic, response synthesized only from Wire1 + Expert2 without checking State2 coverage. Result: one-sided. **Fix:** the both-sides rule is non-negotiable; missing-side acknowledgement is required.
- **YYYY-MM-DD:** Response attributed a position to Pol1 that came from a ThinkTank1 paper, not from Pol1 directly. **Fix:** distinguish "Pol1 said X" from "ThinkTank1 reads Pol1 as saying X."
