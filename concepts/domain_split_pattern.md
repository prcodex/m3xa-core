---
name: domain_split_pattern
description: How sibling domains (Macro / Geo / AI / Region) share infra but stay separated by corpus, soul, and bot
type: concept
applies_to: m3xa-core
status: stub
---

# The domain split pattern

> One pipeline, multiple domains. They share LanceDB, the 7-actor pipeline, the self-awareness loop, and the API keys. They differ in **corpus** (`domain` column on `unified_feed`), **soul** (different expertise modules load), and **distribution** (different Telegram bots, different audiences).

Stub. Full essay covers:

- The `domain` column on `unified_feed` as the primary partition
- Per-domain expertise modules (macro/, geo/, ai/, region/)
- Per-domain bots with separate user filters
- Shared backends, separate corpora
- When to *fork* vs when to *add a domain* — the call ("Is the synthesis style different? Are the sources different? Is the audience different?")
- Cross-domain queries: how the classifier handles "what does the AI literature say about the central bank's communication strategy?"
