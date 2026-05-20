"""Actor 7 — Evaluator. Scores the synthesizer output against a rubric.

Single Haiku call. Output is EvaluationResult; high score gates the
response, low score triggers a regen (one retry max).
"""
from __future__ import annotations

from m3xa_core.schemas import EvaluationResult


def evaluate(query: str, response: str, *, llm: object) -> EvaluationResult:
    """Rubric-based scoring + regen recommendation. Skeleton."""
    raise NotImplementedError
