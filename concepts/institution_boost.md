---
name: institution_boost
description: Multi-entity boost retrieval — how the pipeline reweights vector search when one or more institutions are detected in the query
type: concept
applies_to: m3xa-core
status: stub
---

# Institution boost

> When the user names an institution (`Inst1`, `Pol1`, `Bank2`, …), pure vector similarity is too soft a signal. The boost layer is a second-pass scoring that weights retrieved docs by *how many of the detected institutions they mention*.

Stub. Full essay covers:

- Why vector-only retrieval misses entity-specific docs (semantic overlap with high-frequency macro language overwhelms the entity signal).
- Two-layer search: vector ANN → entity boost reranking.
- Fuzzy alias matching ("BCB" / "central bank" / "Inst1 governor" all match `Inst1`).
- Multi-entity boost when the query names ≥2 entities — co-mention bonus.
- Configuration via `config/retrieval_scoring.yaml`.
