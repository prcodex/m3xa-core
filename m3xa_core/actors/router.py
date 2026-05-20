"""Actor 1.5 — Expertise Router. Picks 1-3 expertises per query."""
from __future__ import annotations

from m3xa_core.schemas import ClassifierOutput, RoutingDecision


def route(classifier_output: ClassifierOutput, *, llm: object) -> RoutingDecision:
    """Single Haiku call reading config/router_prompt.md + expertise descriptions.

    The output schema is a hard contract — downstream actors depend on
    {expertises, confidence, rationale}. Skeleton.
    """
    raise NotImplementedError
