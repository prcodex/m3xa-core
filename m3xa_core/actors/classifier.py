"""Actor 1 — Classifier. Tags a query with topics, entities, intent.

The classifier is a single Haiku call. It is the **first decision** the
pipeline makes about a query, and every actor downstream depends on its
output (routing, retrieval filters, agent hub firing). It is intentionally
cheap — sub-second, single LLM call, ~200 output tokens.

Design notes:

- The output schema is small and stable (`ClassifierOutput`). Adding
  fields is fine; renaming or removing breaks every downstream actor.
- Failure mode is *not* a raise — it's a low-confidence fallback that
  routes to the default expertise. The pipeline never stalls on a bad
  classification.
- Time windows are expressed in hours. Queries with no temporal language
  get `time_window_hours=None`, which the retriever interprets as the
  expertise default.
- Entities are aliased — see `docs/source_naming.md`. A query that
  mentions `Bank1`, `Expert3`, `Inst1` resolves through the entity
  registry; anything else falls back to a content-match heuristic in
  the retriever.
"""
from __future__ import annotations

import json
import re

from m3xa_core.schemas import ClassifierOutput

PROMPT_TEMPLATE = """You are the classifier in a 7-actor intelligence pipeline.
Tag the query with structured metadata. Reply with ONE JSON object and nothing else.

Schema:
{{
  "topics":             [string, ...]  // 1-4 short topic tags (e.g. "rates", "geopolitics")
  "entities":           [string, ...]  // institution / person / country aliases mentioned
  "intent":             string         // "question" | "data" | "summary" | "compare" | "explain"
  "time_window_hours":  integer | null // explicit recency, else null
  "confidence":         float          // 0.0 - 1.0
}}

Rules:
- Topics use the analyst vocabulary, not the user's words.
- Entities use only the registered aliases from `docs/source_naming.md` (Bank1, Expert3, Inst1, CountryA, ...).
- If the query says "today" / "right now" -> 24. "this week" -> 168. "last month" -> 720.
- Confidence reflects how clearly the query fits a known shape. Vague queries get <= 0.5.

Query:
{query}
"""

KEYWORD_FALLBACK = {
    "rates": ("rates", "yield", "yields", "curve", "duration"),
    "fx": ("fx", "currency", "dollar", "euro"),
    "geopolitics": ("war", "conflict", "sanctions", "geopolitical"),
    "fiscal": ("fiscal", "deficit", "debt", "treasury"),
    "monetary": ("monetary", "central bank", "policy rate"),
    "equities": ("equities", "stocks", "stock"),
    "commodities": ("oil", "gas", "gold", "commodity"),
}


def _keyword_fallback(query: str) -> ClassifierOutput:
    """Cheap topic-only classification when the LLM is unavailable.

    Confidence is capped at 0.4 — downstream routers should treat this as
    "best-effort, not a real classification."
    """
    q = query.lower()
    topics = [topic for topic, words in KEYWORD_FALLBACK.items() if any(w in q for w in words)]
    return ClassifierOutput(
        topics=topics or ["general"],
        entities=[],
        intent="question",
        time_window_hours=None,
        confidence=0.4 if topics else 0.2,
    )


def _parse_llm_response(raw: str) -> dict:
    """Tolerant JSON extraction. The LLM sometimes wraps JSON in prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        # ```json ... ``` or ``` ... ```
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        raise ValueError("no JSON object in classifier response")
    return json.loads(match.group(0))


def classify(query: str, *, llm: object) -> ClassifierOutput:
    """Single Haiku call. Returns ClassifierOutput.

    On LLM failure or malformed JSON, falls back to a keyword-only
    classification at <=0.4 confidence — never raises.
    """
    if llm is None:
        return _keyword_fallback(query)

    try:
        raw = llm.complete(  # type: ignore[attr-defined]
            model="claude-haiku-4-5",
            system="Return one JSON object. No prose.",
            user=PROMPT_TEMPLATE.format(query=query),
            max_tokens=400,
            temperature=0.0,
        )
        data = _parse_llm_response(raw)
    except Exception:
        return _keyword_fallback(query)

    return ClassifierOutput(
        topics=list(data.get("topics") or [])[:4],
        entities=list(data.get("entities") or []),
        intent=str(data.get("intent") or "question"),
        time_window_hours=data.get("time_window_hours"),
        confidence=float(data.get("confidence") or 0.0),
    )
