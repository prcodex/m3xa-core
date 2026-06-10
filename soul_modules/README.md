# Soul modules — production souls

This directory contains the **actual production souls** the live M3xA system loads, copied from the running RAG host. See [`concepts/the_house.md`](../concepts/the_house.md) for the metaphor.

Each soul is a monolithic markdown file loaded by `_load_soul(variant)` in `production/m3xa_rag_8550.py` from `/home/ubuntu/argus/config/soul_{variant}.md`, with a 5-minute mtime cache.

## The two production variants

| Variant | File | Audience | Scope |
|---|---|---|---|
| `global` | [`global.md`](./global.md) | `@M3xA_bot` (Telegram) | Global macro, geopolitics, Iran, energy, fiscal, China |
| `brazil` | [`brazil.md`](./brazil.md) | `@M3xa_Brazil_bot` (Telegram) | Brazilian political economy, electoral polls, STF, Selic |

The soul is the **whole** system prompt the synthesizer reads (plus the runtime-injected time / data / agent context blocks).

## What's in each soul

Each variant covers, in document order:

1. **Identity** — who the analyst is, what audience, what language
2. **Persona rules** — never explain plumbing, stay in character
3. **My data** — the source list (Bloomberg, WSJ, Goldman, UBS, Gavekal, Itaú, XP, etc.)
4. **My agents** — Markets, Polymarket, Calendar, Iran Proxies, Boost, Hormuz Monitor, etc.
5. **Data conventions** — FX sign convention, BRL hours, timezone, basis-point rules
6. **Grounding rules** — only cite from context, never invent markets
7. **Time window declaration** — declare the search window at the start
8. **Freshness behavior** — LIVE / RECENT / OLDER bands
9. **Source hierarchy** — tiered, with hard scope filters (Brazil hidden in macro)
10. **Both-sides rule** — Iran coverage requires Iran/Tehran perspective
11. **Response format** — Telegram-mobile constraints, `<pre>` tables, no markdown tables
12. **Chart suggestions** — `<!--CHART:TICKER:RANGE:TYPE-->` tag for server-side image generation
13. **Failure modes** — accumulated corrections from past responses

## Hot reload

The soul is reloaded automatically when its `mtime` changes (5-min cache). Edits propagate without restarting the RAG process. See `_load_soul` in `production/m3xa_rag_8550.py`.

## Frontmatter

The production souls do **not** carry frontmatter — they are loaded raw by `_load_soul()`. Frontmatter in the public-repo template files (`_template_module.md`) is for the didactic decomposition pattern that this repo originally illustrated; the live system collapsed back to monolithic.

## What's in / what's not

- **In:** the actual analyst voice, source list, refusal posture, response format, accumulated failure modes.
- **Not in:** API keys, bot tokens, email passwords, hostnames-with-credentials. Those live in env vars on the host.

## See also

- [`concepts/the_house.md`](../concepts/the_house.md) — the room metaphor (soul / body / mind / memory)
- [`concepts/soul_amendment_engine.md`](../concepts/soul_amendment_engine.md) — how the engine proposes edits and why approval is required
- [`production/m3xa_rag_8550.py`](../production/m3xa_rag_8550.py) — the RAG host that loads these souls (`_load_soul`, lines 72-94)
- [`production/travel_environments.md`](../production/travel_environments.md) — the production environments map
