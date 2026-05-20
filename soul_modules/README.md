# Soul modules

The Soul of the agent. See [`concepts/the_house.md`](../concepts/the_house.md) for the metaphor.

Each soul module is a markdown file with YAML frontmatter. The frontmatter declares when the module loads; the body is the analytical lens the synthesizer reads.

## What's in this directory

This is a **template repository**. The public repo ships:

- [`_template_module.md`](_template_module.md) — a blank module showing the frontmatter shape and the body conventions.

Your private fork adds the actual modules — the editorial voice, the analytical lens for each expertise area, the refusal rules, the output format conventions. None of those belong here.

## The frontmatter

```yaml
---
name: <slug — matches the filename without .md>
description: <one-line summary the router reads to decide whether to load this>
version: <semver>
type: expertise | kernel | scope_filter
applies_to: <domain — e.g. macro, geo, ai, region>
trigger_keywords: [keyword1, keyword2, ...]
trigger_entities: [Inst1, Pol1, ...]
tokens_estimate: <integer>
---
```

## The body conventions

A good soul module covers:

1. **What this lens covers** — and what it doesn't (cross-references to adjacent modules)
2. **Source hierarchy** — which tiers matter for this lens (Wire / Expert / Institutional from `docs/source_naming.md`)
3. **Domain conventions** — terminology, units, common abbreviations the synthesizer should preserve
4. **Analytical framing** — the right way to think about this domain. *This is where the voice lives.*
5. **Output format preferences** — what tables, what charts, what citation style
6. **Failure modes** — corrections accumulated from past responses (these often come from the `soul_amendment_engine`)

## How modules are picked

At query time:

1. The router (Actor 1.5) reads each module's `description` field and picks 1-3 modules matching the query topic.
2. The assembler (Actor 2) concatenates the picked modules into the synthesizer's system prompt.
3. The kernel (`type: kernel`) and any `type: scope_filter` modules are **always loaded** alongside the routed picks.

## What is **never** in this directory

- Real proprietary editorial voice — that's in the reader's private fork
- Real bank/expert names — even as examples
- Real refusal rules tied to specific entities

The `_template_module.md` shows the shape with placeholders.

## See also

- [`concepts/the_house.md`](../concepts/the_house.md) — the room metaphor
- [`concepts/soul_amendment_engine.md`](../concepts/soul_amendment_engine.md) — how the engine proposes edits and why approval is required
