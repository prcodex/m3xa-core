"""Actor 1.5 — Expertise Router. Picks 1-3 expertises per query.

The router reads `ClassifierOutput` and decides which expertises the
assembler should concatenate into the system prompt. Output is a hard
contract: `expertises: list[str]`, `confidence: float`, `rationale: str`.

Two-tier decision:

1. **Fast path** — pure keyword/topic mapping against expertise frontmatter.
   Cheap, deterministic, no LLM call. If a single expertise covers the
   query cleanly, ship that.
2. **Slow path** — single Haiku call when the query is ambiguous (multiple
   expertises matched, or none matched, or classifier confidence < 0.5).

A query that mixes scopes (e.g. macro + a country lens) returns multiple
expertises; the assembler concatenates them in the order returned.
"""
from __future__ import annotations

import json
import re

from m3xa_core.schemas import ClassifierOutput, RoutingDecision

# The didactic expertise inventory mirrors `expertises/*.md` in the repo.
# Each value is a topic set; if the classifier's topics intersect, the
# expertise is a candidate.
EXPERTISE_TOPICS: dict[str, set[str]] = {
    "macro_lens": {"rates", "fx", "monetary", "fiscal", "central bank"},
    "geo_lens": {"geopolitics", "war", "conflict", "sanctions"},
}
KERNEL = "m3xa_kernel"  # always loaded; never returned by the router

PROMPT_TEMPLATE = """You are the expertise router. Pick 1-3 expertise modules from this list:

{expertise_list}

The kernel ({kernel}) is always loaded; do NOT include it.

Input from the classifier:
- topics:    {topics}
- entities:  {entities}
- intent:    {intent}

Reply with ONE JSON object:
{{
  "expertises": [string, ...],   // 1-3 names from the list above
  "confidence": float,            // 0.0 - 1.0
  "rationale":  string            // <= 200 chars
}}
"""


def _fast_path(classifier_output: ClassifierOutput) -> RoutingDecision | None:
    """Pure topic-overlap routing. Returns None if ambiguous."""
    topics = {t.lower() for t in classifier_output.topics}
    matches = [name for name, tset in EXPERTISE_TOPICS.items() if topics & tset]
    if len(matches) == 1 and classifier_output.confidence >= 0.6:
        return RoutingDecision(
            expertises=matches,
            confidence=min(0.9, classifier_output.confidence),
            rationale=f"single-expertise match on topics={sorted(topics & EXPERTISE_TOPICS[matches[0]])}",
        )
    return None


def _parse_llm(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        raise ValueError("no JSON in router response")
    return json.loads(match.group(0))


def _default_decision() -> RoutingDecision:
    """Last-resort routing: macro lens covers most macro queries."""
    return RoutingDecision(
        expertises=["macro_lens"],
        confidence=0.3,
        rationale="default routing — classifier returned nothing actionable",
    )


def route(classifier_output: ClassifierOutput, *, llm: object) -> RoutingDecision:
    """Pick 1-3 expertises. Fast path on a clean topic match; LLM otherwise.

    Output schema is a hard contract. Renaming `expertises` / `confidence` /
    `rationale` breaks the assembler.
    """
    fast = _fast_path(classifier_output)
    if fast is not None:
        return fast

    if llm is None:
        return _default_decision()

    try:
        raw = llm.complete(  # type: ignore[attr-defined]
            model="claude-haiku-4-5",
            system="You are a router. Return one JSON object.",
            user=PROMPT_TEMPLATE.format(
                expertise_list="\n".join(f"- {e}" for e in sorted(EXPERTISE_TOPICS)),
                kernel=KERNEL,
                topics=classifier_output.topics,
                entities=classifier_output.entities,
                intent=classifier_output.intent,
            ),
            max_tokens=300,
            temperature=0.0,
        )
        data = _parse_llm(raw)
    except Exception:
        return _default_decision()

    picks = [e for e in (data.get("expertises") or []) if e in EXPERTISE_TOPICS][:3]
    if not picks:
        return _default_decision()
    return RoutingDecision(
        expertises=picks,
        confidence=float(data.get("confidence") or 0.5),
        rationale=str(data.get("rationale") or "router decision"),
    )
