---
name: golden_exchange
description: How human-labeled exchanges become persistent retrieval boosts — the #gold command pattern
type: concept
applies_to: m3xa-core
status: stub
---

# Golden exchange

> Sometimes a conversation captures something the system doesn't know how to surface on its own. The `#gold` command pattern lets a human tag an exchange, extract the learning (THESIS / DATA / FRAMEWORK / CORRECTION / INSIGHT), and persist it. The next time a related query comes in, the learning is in the retrieval context.

Stub. Full essay covers:

- The five learning types and how the extractor (Haiku) classifies each
- Storage: `golden_exchanges.db` (SQLite), one row per learning, tagged by topic
- Retrieval injection: keyword-match at query time, top-K learnings prepended to context
- Relevance decay: learnings >30 days get reduced weight (never auto-deleted)
- Commands: `#goldN`, `#gold remove`, `#goldlist`, `#goldstats`
- Anti-pattern: tagging too much — the learnings file fills with noise
