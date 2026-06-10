# Soul modules

The Soul of the agent. See [`concepts/the_house.md`](../concepts/the_house.md) for the metaphor.

This directory follows the **production layout** of the live system: each soul is a **monolithic markdown file per variant**, not a set of decomposed voice / scope-filter / lens modules. The router picks the variant at query time; the loaded soul is the *whole* system prompt the synthesizer reads (plus the runtime-injected time / data / agent context blocks).

## The two variants in this repo

| Variant | File | Audience | Scope |
|---|---|---|---|
| `global` | [`global.md`](./global.md) | `@MainBot` | Global macro, geopolitics, energy, fiscal, CountryB |
| `brazil` | [`brazil.md`](./brazil.md) | `@RegionalBot` | CountryA-specific macro, fiscal, political economy |

Each soul is a single file that covers:

1. **Identity** — who the analyst is, what audience
2. **Voice** — plain prose, lead with the answer, no boilerplate
3. **Length tiers** — quick / data / analytical / brainstorm caps
4. **Table formatting** — width and shape rules
5. **Source hierarchy** — tiered, with explicit aliases from `docs/source_naming.md`
6. **Citation discipline** — `[Source · YYYY-MM-DD]` requirement
7. **Both-sides rule** (geopolitical only) — mandatory missing-side acknowledgement
8. **Temporal reasoning** — how to use injected current time + calendar
9. **Local conventions** (regional variants only) — terminology, vocabulary
10. **Refusal rules** — what to decline and how
11. **Failure modes** — corrections accumulated from past responses (these often come from the `soul_amendment_engine`)

The soul is hot-reloadable in production with a 5-minute cache (see `_load_soul` in `concepts/the_house.md` for the pattern). Edits propagate without a restart.

## Why monolithic, not modular

The didactic temptation is to decompose: separate "voice" / "refusal" / "both-sides" / "lens" files that compose at runtime. The live system tried that and converged on monolithic-per-variant because:

1. **Edit locality.** When a failure-mode correction lands, you edit one file, not five.
2. **Diff legibility.** A soul change is one diff, not a multi-file change set with composition order to reason about.
3. **Hot reload simplicity.** One file = one `mtime` check = one cache key per variant.
4. **Composition order is implicit.** Inside one file, sections are read in document order; no separate "assembler" loading rule needs to be maintained alongside the modules.

The composition logic (voice + refusal + scope filter + lens) still exists conceptually — it just lives **inside** the soul rather than as separate files. Section headings inside `global.md` and `brazil.md` mirror what would have been separate modules in a decomposed layout.

## The frontmatter

```yaml
---
name: <variant name — matches filename without .md>
description: <one-line summary>
version: <semver>
type: kernel
applies_to: <macro | region | all>
trigger_keywords: []
trigger_entities: []
tokens_estimate: <integer>
---
```

`trigger_keywords` and `trigger_entities` are empty for both variants — the router picks the variant by **scope** (bot / domain / explicit filter), not by keyword. See `m3xa_core/actors/router.py` for the scope-detection logic.

## How the variant is picked

At query time:

1. The classifier tags the query.
2. The router decides scope (`global` vs `regional`) from the bot context, explicit `#brazil` / `#macro` shortcuts, or scope-keyword detection.
3. The assembler loads the matching variant file in full.
4. Runtime context (current time, calendar window, retrieved docs, agent blocks) is injected after the soul.
5. One synthesizer call.

## What's never in this directory

- Real source names — even as examples. Use only the aliases from `docs/source_naming.md`.
- Real bot tokens, API keys, hostnames, or recipient addresses.
- The actual proprietary editorial voice of the live system. The souls here are the *pattern*, not the live prompt.
- The actual entity registry contents.

## The template

[`_template_module.md`](_template_module.md) — a frontmatter + body shape for **a new soul variant** (e.g. adding an AI-specialist variant). The template predates the monolithic decision and uses the older "expertise module" framing; readers extending the pattern should follow the structure of `global.md` and `brazil.md` instead.

## See also

- [`concepts/the_house.md`](../concepts/the_house.md) — the room metaphor (soul / body / mind / memory)
- [`concepts/soul_amendment_engine.md`](../concepts/soul_amendment_engine.md) — how the engine proposes edits and why approval is required
- [`docs/source_naming.md`](../docs/source_naming.md) — the alias taxonomy used throughout the souls
