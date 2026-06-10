---
name: regional_lens
description: Loads when the query is about RegionX (the Gulf / Levant / Mashreq area) — bilateral state dynamics, proxy networks, energy chokepoints, and regional alignment shifts
version: 0.1.0
type: expertise
applies_to: geo
trigger_keywords: [RegionX, Strait, proxy, Gulf, sanctions, embargo, ceasefire, chokepoint]
trigger_entities: [Pol3, ThinkTank2, State2]
tokens_estimate: 750
---

# Regional lens (RegionX)

> The RegionX-specialist lens. Reads bilateral dynamics, proxy networks, and energy chokepoints with both-sides discipline. Treats State2 framing as a required input, not as adversarial noise.

## What this covers

- Bilateral and multilateral state dynamics inside RegionX
- Proxy networks and their links to state principals
- Energy chokepoints (Straits, pipeline routes, refinery/export terminal capacity)
- Sanctions regimes targeting actors in RegionX and their workarounds
- Ceasefire / escalation dynamics on the regional axis

## What this does NOT cover

- Great-power competition outside RegionX → see `geo_lens.md`
- Pure energy-market pricing without a geopolitical driver → see `energy_lens.md`
- CountryB or CountryA domestic policy → see `china_lens.md` and `macro_lens.md`

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire3** — wires for breaking events; Wire3 for regional vernacular reporting
2. **Expert6** — independent RegionX specialist; **highest-signal tier for this lens**
3. **Expert2** — generalist geopolitical analyst for great-power framing
4. **ThinkTank1, ThinkTank2** — DC-based think-tank framing (hawkish + restraint-leaning; load both)
5. **State1, State2** — state-aligned media on each side of the regional axis; **both required**
6. **Wire2** — for European framing on sanctions

## The both-sides rule (mandatory)

This lens inherits the both-sides rule from `geo_lens.md` and applies it with no exceptions.

For any adversarial topic in RegionX:

1. The response **must** include framing from at least two state-aligned sources.
2. If retrieval is one-sided, the response says so explicitly with the missing side named:

   > "Retrieved coverage is heavily weighted to [side A] framing. [State2]'s coverage of `<this specific framing>` — which usually emphasizes `<typical points>` — is not present in retrieval; treat this as one-sided."

3. The missing-side acknowledgement is not optional. The retriever's filters should usually load both; when they don't, the synthesizer's honesty is the fallback.

## Analytical framing

- **Distinguish principal from proxy.** A proxy action is the principal's action only after the principal has implicitly or explicitly authorized it. Default attribution to proxies, then promote to principals when the evidence supports it.
- **Chokepoints are leverage, not intent.** The capacity to close a Strait is not the plan to close it. Cite both the capacity and the posture indicators; never one alone.
- **Track the narrative axis, not the kinetic axis.** Most regional escalations are narrated for weeks before they kinetic-escalate. Watch State1 vs. State2 framing convergence as the early signal.
- **Sanctions workarounds are the real economy.** Headline sanctions and effective sanctions differ widely. The interesting question is always the workaround — who's providing it, at what price, with what stability.

## Output format

- Lead with the answer.
- Then: `What happened` · `Reading from side A (with sources)` · `Reading from side B (with sources)` · `What's escalating, what's de-escalating, what to watch`.
- Cite each side's sources separately; never blend them into a single attribution.
- Maximum 750 words.

## Failure modes captured

- **YYYY-MM-DD:** Response synthesized side-A framing only, citing only Wire1 + Expert6 + ThinkTank1. **Fix:** the both-sides rule was violated; State2 framing should have been loaded or explicitly named as missing.
- **YYYY-MM-DD:** Response attributed a proxy attack to a state principal without evidence of authorization. **Fix:** default attribution to the proxy; the upgrade to principal requires explicit evidence cited.
