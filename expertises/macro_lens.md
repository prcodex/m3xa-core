---
name: macro_lens
description: Loads when the query is about rates, FX, central banks, inflation, growth, fiscal policy — at the macroeconomic level
version: 0.1.0
type: expertise
applies_to: macro
trigger_keywords: [rates, FX, inflation, CPI, GDP, central bank, fiscal, deficit, debt]
trigger_entities: [Inst1, Inst2, Inst3, Pol1]
tokens_estimate: 700
---

# Macro lens

> The macroeconomic lens. Reads policy decisions, market reactions, and consensus shifts in terms of what they imply for the macro picture six to twelve months out.

## What this covers

- Central bank policy actions and the implied reaction function
- Rates / FX market action interpreted as policy expectations
- Inflation and growth releases vs consensus
- Fiscal stance (deficits, debt issuance, fiscal-monetary interaction)
- Cross-country macro comparisons

## What this does NOT cover

- Pure equity strategy → see `market_lens.md`
- Geopolitical events as such (only their macro implications appear here) → see `geo_lens.md`
- Day-to-day market microstructure → see `market_lens.md`

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire2** — central bank press releases, statements, minutes
2. **Expert1, Expert3** — independent macro analysts; especially Expert3 for long-arc framing
3. **Bank1, Bank2, Bank5** — bulge-bracket house views (consensus framing)
4. **Bank6** — for region-specific commentary
5. **Macro1** — boutique macro for "what the smart money is reading"

## Analytical framing

- **Central banks have reaction functions, not opinions.** A surprise hike isn't about the central banker's mood — it's about how the function reads new data.
- **Markets price expectations, then surprise.** Distinguish "the market already knew this" from "the market is repricing."
- **Real rates matter more than nominal rates.** When citing a rate move, also note the inflation print or expectation that contextualizes it.
- **Fiscal and monetary interact.** A central bank that has to coexist with a profligate fiscal authority operates under different constraints than one that doesn't.
- **Consensus is a moving target.** "Hawkish vs dovish" is meaningful only relative to *current* consensus, not absolute policy stance.

## Output format

- One-sentence answer first.
- Then `Why this matters`, `What's priced`, `What to watch` — three short paragraphs.
- Cite every data point: `CPI YoY 3.2% [Inst1 · 2026-04-15]`.
- Maximum 600 words.

## Failure modes captured

- **YYYY-MM-DD:** When asked about Inst1's next move, the response confidently asserts a hike without checking whether the policy meeting is in the user's implicit time window. **Fix:** if no meeting is scheduled within the time window, lead with "Inst1 has no scheduled meeting in this window; the question is about market pricing, not next decision."
- **YYYY-MM-DD:** When retrieved docs only have Bank1/Bank2 (consensus) and the user asks for *non-consensus* views, the response synthesizes a fake non-consensus position. **Fix:** if Expert1/Expert3 coverage is missing, say "non-consensus views are not in retrieval for this query."
