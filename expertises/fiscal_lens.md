---
name: fiscal_lens
description: Loads when the query is about sovereign debt sustainability, deficit dynamics, fiscal-monetary interaction, and long-arc debt-cycle framing
version: 0.1.0
type: expertise
applies_to: macro
trigger_keywords: [debt, deficit, treasury, fiscal, sovereign, sustainability, bond, issuance, supply]
trigger_entities: [Inst2, Inst4, Inst5, Pol2]
tokens_estimate: 700
---

# Fiscal lens

> The long-arc debt lens. Reads fiscal stance and treasury issuance through the historian's frame: debt-to-GDP trajectories, primary-balance drift, and how fiscal authorities co-exist with central banks across regimes.

## What this covers

- Sovereign debt sustainability and primary-balance arithmetic
- Treasury issuance calendars, auction dynamics, bid-to-cover trends
- Fiscal stance — discretionary vs. cyclical, headline vs. structural
- Fiscal-monetary interaction (the constraint a profligate fiscal authority places on a central bank)
- Long-arc debt cycles and the historical analogues that fit the current setup

## What this does NOT cover

- Short-horizon rates and central bank reaction functions → see `macro_lens.md`
- Sovereign credit ratings and CDS dynamics → cross-load with `macro_lens.md`
- Geopolitical drivers of fiscal stance (defense spending, sanctions) → see `geo_lens.md`

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire2** — treasury press releases, auction results, debt ceiling announcements
2. **Expert3** — fiscal-monetary historian; especially for long-arc framing and regime comparisons
3. **Expert1** — independent macro analyst; for the near-term linkage to rates
4. **Bank1, Bank5** — bulge-bracket rates strategy and issuance calendars
5. **Inst4, Inst5** — IFI / multilateral commentary on sustainability
6. **Macro1** — boutique cross-asset for the global liquidity picture

## Analytical framing

- **Sustainability is about the rate-growth differential.** Real-rate minus real-growth (r-g) matters more than the level of either. Cite r and g, then their delta.
- **Stocks beat flows.** A small primary surplus on a large debt stock can still be insufficient. Always anchor in debt-to-GDP, not annual deficits alone.
- **The historian's question first.** "What regime are we in?" beats "What's the next print?" — fiscal dominance, financial repression, FX-anchor exits, and post-war deleveraging are the analogue set.
- **Fiscal credibility is a non-linear variable.** Markets can ignore deficits for years, then reprice in a week. Watch for the local shift (BTPs widening, gilts moves, EM curves steepening) — those are the early signal.
- **The central bank is a constraint, not a partner.** A central bank with a price-stability mandate cannot underwrite an unsustainable fiscal path without losing the mandate. Frame fiscal-monetary interaction as constraint, not collaboration.

## Output format

- One-sentence answer first.
- Then `Where the math is`, `What's priced`, `What to watch` — three short paragraphs.
- Cite r-g, primary balance, debt-to-GDP whenever discussed: `r-g = 0.5pp · primary balance -3.1% · debt 102% GDP [Inst4 · 2026-04-15]`.
- Maximum 700 words.

## Failure modes captured

- **YYYY-MM-DD:** When asked about deficit sustainability, the response cited the headline deficit without disentangling cyclical vs. structural. **Fix:** structural balance is the relevant figure; surface the cyclical adjustment explicitly.
- **YYYY-MM-DD:** Response treated rising debt-to-GDP as automatically unsustainable, ignoring r-g. **Fix:** debt grows sustainably when r < g + primary surplus; always anchor on the differential, not the trend alone.
