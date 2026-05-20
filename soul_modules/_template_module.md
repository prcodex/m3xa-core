---
name: _template_module
description: A short, specific description the router reads to pick this module for a query. Replace with your module's actual scope.
version: 0.1.0
type: expertise
applies_to: macro
trigger_keywords: [keyword1, keyword2, keyword3]
trigger_entities: [Inst1, Inst2]
tokens_estimate: 600
---

# Module name (replace)

> One sentence summary of the analytical lens this module brings.

## What this module covers

Three to five bullets describing the scope of this lens. Be specific — the router reads the `description` frontmatter, but the synthesizer reads this body, and the boundary between "what's in" and "what's out" is what makes the module composable.

- Topic 1 this module owns
- Topic 2 this module owns
- Topic 3 this module owns

## What this module does NOT cover

- Topic adjacent-1 → see `<sibling_module>.md`
- Topic adjacent-2 → see `<sibling_module>.md`

The "not for" list is what keeps modules from overlapping. Two modules that both fire on the same query are usually a sign one of them needs a tighter "not for".

## Source hierarchy

When this module fires, the retriever should weight sources in this order:

1. **Wire1, Wire2** — real-time wire services for breaking events
2. **Expert1, Expert2** — independent expert analysts for interpretation
3. **Bank1, Bank2** — bulge-bracket bank research for consensus framing
4. **State1** — state-aligned media for adversarial framing (geopolitical lens)

Aliases come from `docs/source_naming.md`.

## Analytical framing

This is where the *voice* lives. The synthesizer uses this section to know HOW to read the retrieved docs.

Examples of framings to write here (replace with your domain):

- "Treat market reactions as derivative of policy, not as policy."
- "Distinguish *consensus shift* from *consensus volatility*."
- "Always identify the central bank's reaction function before predicting its next move."

A good framing section produces consistent responses across queries about the same topic. A bad framing section is a list of unrelated rules.

## Output format

- Lead with the headline answer in one sentence.
- Three sections: `What happened`, `What it means`, `What to watch`.
- Cite every quantitative claim with a `[Source · YYYY-MM-DD]` tag.
- Maximum 600 words unless the query asks for depth.

## Refusal rules

When NOT to answer:

- If the retrieved docs are >7 days old and the user asked about a current event → caveat the staleness explicitly
- If the user asks about a specific named individual not in the entity registry → name uncertainty rather than guessing
- If the retrieved docs disagree and the disagreement is the answer → say so; don't synthesize a false consensus

## Failure modes

Bugs the soul has learned from past responses. New entries get appended by the `soul_amendment_engine` (with human approval).

- *<YYYY-MM-DD>*: When responding to questions about topic X without docs from source-tier-N, the response hedges insufficiently. **Fix:** if tier-N coverage is missing, lead with "Tier-N sources are not in retrieval for this query; this response reflects tier-(N+1)+ only."
