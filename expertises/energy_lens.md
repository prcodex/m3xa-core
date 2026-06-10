---
name: energy_lens
description: Loads when the query is about oil, gas, coal, refined products, energy transition, OPEC dynamics, pipeline infrastructure, and commodity-cycle framing
version: 0.1.0
type: expertise
applies_to: macro
trigger_keywords: [oil, gas, OPEC, crude, Brent, WTI, LNG, refinery, pipeline, energy, commodity, supply, demand]
trigger_entities: [Inst3]
tokens_estimate: 700
---

# Energy lens

> The commodity-cycle lens. Reads oil, gas, and refined-product moves in terms of physical supply/demand, OPEC reaction functions, and the long-arc energy transition. Distinguishes price action from inventory action.

## What this covers

- Crude and refined-product price action (Brent, WTI, distillates, gasoline cracks)
- OPEC and OPEC+ supply decisions, compliance, spare capacity
- Natural gas — pipeline vs. LNG dynamics, regional spreads (Henry Hub, TTF, JKM)
- Inventory cycles (commercial, strategic, floating storage)
- Energy transition — capex flows, renewable build-out, the gap between aspiration and infrastructure

## What this does NOT cover

- Pure macro impact of energy prices (CPI pass-through, growth drag) → see `macro_lens.md`
- Energy geopolitics as such (sanctions regimes, Strait closures) → see `geo_lens.md` and `regional_lens.md`
- Equity-level views on energy companies → not in this repo's scope

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire2** — wire breaks for OPEC announcements, pipeline outages, refinery incidents
2. **Expert4** — independent energy specialist; the most-cited tier for interpretation
3. **Bank1, Bank5** — bulge-bracket commodities desks for inventory data
4. **Macro1** — boutique cross-asset for energy-as-macro framing
5. **State1, State2** — state-aligned media when a producer-country narrative matters

## Analytical framing

- **Distinguish flow from stock.** A barrel produced today is a flow; floating storage is a stock. Price reacts to expected flow; backwardation/contango reflect stock pressure.
- **OPEC has a reaction function, not a fixed quota.** Production decisions respond to inventory levels, spare capacity, fiscal needs of member states, and the marginal-barrel competition. Frame each cut/hike as a reaction.
- **Spare capacity is the asymmetry.** Low spare capacity makes the curve sensitive to small supply shocks. Track effective spare capacity (excluding stranded barrels), not nameplate.
- **The transition is uneven.** Renewables build-out is years ahead of grid-scale storage and transmission. Don't extrapolate generation capacity to delivered energy.
- **Refined-product spreads are the leading indicator.** Cracks (3-2-1, gasoil) move before crude when demand turns; refining margins price recession faster than crude itself.

## Output format

- One-sentence answer first.
- Then `Where the physical sits`, `Where the curve sits`, `What to watch` — three short paragraphs.
- Cite price + reference month: `Brent Q3 +2.4% · 3-2-1 crack -$1.1/bbl [Wire1 · 2026-04-15]`.
- Maximum 700 words.

## Failure modes captured

- **YYYY-MM-DD:** Response cited OPEC nameplate capacity instead of effective spare. **Fix:** spare capacity excludes barrels that can't be brought online within 90 days at sustainable rates; always use effective.
- **YYYY-MM-DD:** Response extrapolated a single inventory print without checking SPR vs. commercial split. **Fix:** SPR draws/releases distort the headline; separate explicitly.
