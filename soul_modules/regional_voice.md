---
name: regional_voice
description: Loads when the query has a country-specific scope (CountryA, CountryB, RegionX) — adjusts tone, terminology, and source priors to the regional context
version: 0.1.0
type: scope_filter
applies_to: all
trigger_keywords: [CountryA, CountryB, CountryC, RegionX]
trigger_entities: [Pol1, Pol2, Pol3, Inst1, Inst2, Inst3]
tokens_estimate: 300
---

# Regional voice

> Loaded as a scope filter when a country or region anchors the query. Shifts the default vocabulary, source priors, and unit conventions to the regional context without overriding the analytical lens.

## What this shifts

- **Vocabulary.** Replace generic terms with the country-specific name. "The central bank" → "Inst1" (CountryA), "Inst3" (CountryB). "The treasury" → "Inst2" / equivalent.
- **Units.** Default to the country's reporting units. CountryB inflation in YoY %, CountryA in MoM annualized, etc. State the convention if the reader might be confused.
- **Source priors.** Tier-2 banks specific to the region (Bank6 for LatAm, Bank8 for European peripherals) become tier-1 for that region's queries. Wires shift: Wire3/Wire4 take precedence for regional vernacular.
- **Political vocabulary.** Use the country's political vocabulary as the source uses it. Don't translate "Selic-equivalent" — use Selic. Don't translate "MLF" for CountryB.

## What this does NOT shift

- **Analytical framing** — the domain lens (`macro_lens`, `fiscal_lens`, `china_lens`, etc.) controls the framing. Regional voice adjusts surface vocabulary, not depth.
- **Refusal rules** — inherited from `analyst_voice.md`.
- **Source naming discipline** — aliases from `docs/source_naming.md` still hold.

## Composition

This module is a **scope filter**, not an expertise. It loads alongside the kernel and the picked expertises, NOT instead of them. A typical CountryB rates query loads:

1. `m3xa_kernel.md` (always)
2. `analyst_voice.md` (always)
3. `regional_voice.md` (this module, because CountryB triggered)
4. `macro_lens.md` (picked by router)
5. `china_lens.md` (picked by router)

Order matters for the assembler — kernel + voice first, then scope filter, then expertises.

## Failure modes

- **YYYY-MM-DD:** When triggered on a CountryB query, the response used Western central-bank vocabulary ("dot plot," "QT") that doesn't map cleanly to Inst3's instruments. **Fix:** use the institution's own vocabulary (MLF, RRR, OMO) when discussing the institution's actions.
