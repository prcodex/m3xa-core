"""Actor 4 — Retriever. Vector search over unified_feed + entity boost reranking.

Reads `ClassifierOutput.entities` and `time_window_hours`, builds the
filter expression for the `VectorDBBackend`, runs the search, then
reranks with the **institution boost** pattern from
`concepts/institution_boost.md`:

1. Embed the query (single embedding call).
2. Vector search top_k *3 over rows where `has_vector > 0` AND the time
   filter holds AND (optionally) the domain matches.
3. Convert vector distance to similarity = 1 - (d / max_d).
4. If the classifier resolved one or more entities, fetch additional
   rows that *mention* the entity (substring on text + keywords),
   prepend them, dedupe by id.
5. Return the top_k blended.

The fuzzy-match step uses strict substring (case-insensitive) on every
known alias variant of a resolved entity. There is no Levenshtein —
substring is fast, predictable, and the alias table is hand-curated.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from m3xa_core.schemas import ClassifierOutput, RetrievedDoc

# Entity alias table — substring match variants per registered alias.
# Real systems load this from `config/entity_registry.yaml`; here it ships
# inline so the retriever has something to work with out of the box.
ENTITY_VARIANTS: dict[str, list[str]] = {
    "Bank1": ["Bank1"],
    "Bank2": ["Bank2"],
    "Expert1": ["Expert1"],
    "Expert3": ["Expert3"],
    "Inst1": ["Inst1", "central bank of CountryA"],
    "CountryA": ["CountryA"],
}


def _build_filter(
    classifier_output: ClassifierOutput,
    *,
    domain: str = "default",
    default_window_hours: int = 168,
) -> str:
    """Build a LanceDB filter expression.

    `has_vector > 0` is invariant — never search un-vectorized rows.
    Time window defaults to one week when the classifier didn't extract
    one explicitly.
    """
    hours = classifier_output.time_window_hours or default_window_hours
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    iso = cutoff.isoformat()
    return (
        f"has_vector > 0 "
        f"AND domain = '{domain}' "
        f"AND published_at >= timestamp '{iso}'"
    )


def _institution_boost(
    base: list[RetrievedDoc],
    entity_keys: list[str],
    *,
    boost_n: int = 5,
) -> list[RetrievedDoc]:
    """Prepend rows that mention any resolved entity, dedupe by id.

    Substring match on the doc's text. Cheap, no second vector call.
    The retriever returns *up to* `boost_n` boosted rows ahead of the
    semantic ranking — the synthesizer still sees the base list after.
    """
    if not entity_keys:
        return base

    variants: list[str] = []
    for key in entity_keys:
        variants.extend(ENTITY_VARIANTS.get(key, [key]))

    def mentions(doc: RetrievedDoc) -> bool:
        haystack = doc.text.lower()
        return any(v.lower() in haystack for v in variants)

    boosted = [d for d in base if mentions(d)][:boost_n]
    seen = {d.id for d in boosted}
    rest = [d for d in base if d.id not in seen]
    return boosted + rest


def retrieve(
    classifier_output: ClassifierOutput,
    *,
    embeddings: object,
    vector_db: object,
    top_k: int = 20,
    domain: str = "default",
) -> list[RetrievedDoc]:
    """Vector search + entity boost. Returns up to top_k docs."""
    if embeddings is None or vector_db is None:
        return []

    # Build the query embedding. We embed the topic + intent rather than the
    # raw query — keeps the query vector closer to the corpus distribution.
    query_text = " ".join(classifier_output.topics) or classifier_output.intent
    query_vector = embeddings.embed(query_text)  # type: ignore[attr-defined]

    filter_expr = _build_filter(classifier_output, domain=domain)
    raw = vector_db.search(  # type: ignore[attr-defined]
        query_vector=query_vector,
        filter_expr=filter_expr,
        top_k=top_k * 3,
    )

    # Vector backends usually return _distance; convert to a 0..1 similarity.
    if raw:
        max_d = max(d.score for d in raw) or 1.0
        raw = [
            RetrievedDoc(
                id=d.id,
                text=d.text,
                source=d.source,
                published_at=d.published_at,
                score=1.0 - (d.score / max_d),
                domain=d.domain,
                metadata=d.metadata,
            )
            for d in raw
        ]

    blended = _institution_boost(raw, classifier_output.entities)
    return blended[:top_k]
