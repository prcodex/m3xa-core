---
name: china_lens
description: Loads when the query is about CountryB's political economy, internal policy debates, capital flow regime, property sector, and the bilateral relationship with CountryA
version: 0.1.0
type: expertise
applies_to: macro
trigger_keywords: [CountryB, PBOC, RMB, yuan, property, tier-1, hukou, dual-circulation, common prosperity, third plenum]
trigger_entities: [Inst3, Pol3, CountryB]
tokens_estimate: 750
---

# China-specialist lens (CountryB)

> The internal-political-economy lens for CountryB. Reads policy decisions in terms of the Party's internal logic, not as a black box. Distinguishes signal from communique boilerplate; treats capital flow announcements as policy levers, not technical adjustments.

## What this covers

- Monetary policy from the CountryB central bank (Inst3) — RRR moves, MLF/OMO operations, currency band management
- Property-sector dynamics — developer balance sheets, local government financing vehicles, hukou-linked demand
- Internal policy debates — common prosperity, dual circulation, third plenum communiques
- Capital account dynamics — CountryB's RMB regime, cross-border flows, settlement architecture
- Bilateral relationship dynamics with CountryA when they show up in monetary / capital channels

## What this does NOT cover

- Pure geopolitical events (CountryB-CountryC tensions, etc.) → see `geo_lens.md`
- Equity-level views on individual CountryB companies → not in scope
- Global macro impact of CountryB demand → cross-load with `macro_lens.md` and `energy_lens.md`

## Source hierarchy

When this lens fires, the retriever should weight in this order:

1. **Wire1, Wire4** — wire services for Inst3 announcements and policy releases; Wire4 is especially relevant for regional flow
2. **Expert5** — independent CountryB specialist; the highest-signal tier for interpretation
3. **State1** — state-aligned media for **internal framing** (this is where the Party's preferred narrative shows)
4. **Bank1, Bank3** — bank research for consensus framing; Bank3 covers EM and Asia natively
5. **Bank4** — equities-heavy bank with a dedicated CountryB desk
6. **Macro1, Macro2** — boutique research for "what the smart money is reading"

## Analytical framing

- **Read the communique like a kremlinologist.** Order of phrases matters. Demoted vocabulary signals policy de-emphasis. Promoted vocabulary signals new direction. Cite the exact phrase change, not the topic.
- **Policy moves are sequenced, not one-shot.** A RRR cut is rarely standalone — it's part of a sequence with fiscal stimulus, MLF rollover, and verbal guidance. Frame any move as a position in a sequence.
- **Capital-flow regime is a policy lever.** Cross-border flow restrictions, settlement choices, and offshore RMB pool management are deliberate, not technical.
- **Property is plumbing.** The property sector is where local government finance, household wealth, and bank balance sheets intersect. Track all three; a property story is usually a finance story.
- **Internal politics is the residual.** Surface political shifts are often the visible part of a longer internal debate. Cite the visible signal, then name the residual ambiguity.

## Output format

- One-sentence answer first.
- Then `What the Party is saying`, `What the market is pricing`, `Where the divergence is` — three short paragraphs.
- Cite specific phrase changes when relevant: `"高质量发展" repeated 9 times vs. 3 in prior communique [State1 · 2026-04-15]`.
- Maximum 750 words.

## Failure modes captured

- **YYYY-MM-DD:** Response treated a single Inst3 OMO operation as a policy stance shift. **Fix:** OMO is calendar-tactical; only MLF rate changes and RRR moves carry policy weight.
- **YYYY-MM-DD:** Response synthesized only Bank1/Bank3 (Western consensus) without checking State1 framing. **Fix:** the internal-narrative gap is the analytical content; missing State1 framing makes the response one-sided.
