"""Actor 7 — Evaluator. Scores the synthesizer output against a rubric.

Single Haiku call. Output is `EvaluationResult` with a 0-10 score, the
rubric notes, and a regen recommendation. Pipeline contract:

- score >= 7.0  -> ship the response
- 6.0 - 6.99    -> ship with a warning header
- < 6.0         -> regen recommended (one retry max upstream)

The rubric weights are tuned for an analyst voice. Editorial quality
(clarity, relevance, precision, source attribution, completeness) is
balanced; precision and source attribution are slightly lower-weighted
because the **self_evaluator** runs structural checks on those in a
separate pass — double-counting them here would over-penalize.
"""
from __future__ import annotations

import json
import re

from m3xa_core.schemas import EvaluationResult

DIMENSIONS = ("clarity", "relevance", "precision", "sources", "completeness")
WEIGHTS = {
    "clarity": 0.25,
    "relevance": 0.25,
    "precision": 0.20,
    "sources": 0.15,
    "completeness": 0.15,
}
REGEN_THRESHOLD = 6.0

PROMPT_TEMPLATE = """You are the evaluator in a 7-actor analyst pipeline.
Score the response 0-10 on each rubric dimension and reply with ONE JSON object.

Schema:
{{
  "clarity":      {{"score": float, "issue": string}},
  "relevance":    {{"score": float, "issue": string}},
  "precision":    {{"score": float, "issue": string}},
  "sources":      {{"score": float, "issue": string}},
  "completeness": {{"score": float, "issue": string}}
}}

Rubric:
- clarity      — Is the response easy to read? Numbers explained? No jargon dumps?
- relevance    — Does it answer the actual question, not an adjacent one?
- precision    — Internally consistent? Any contradictions or sloppy claims?
- sources      — Aliased sources cited? Claims attached to retrieved docs?
- completeness — Does it cover what a competent analyst would expect?

Query:
{query}

Response:
{response}
"""


def _parse(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        raise ValueError("no JSON in evaluator response")
    return json.loads(match.group(0))


def _weighted_score(scores: dict[str, float]) -> float:
    return sum(scores.get(dim, 0.0) * WEIGHTS[dim] for dim in DIMENSIONS)


def _format_notes(scores: dict[str, float], issues: dict[str, str]) -> str:
    lines = []
    for dim in DIMENSIONS:
        score = scores.get(dim, 0.0)
        issue = issues.get(dim, "").strip()
        flag = " <" if score < 6.0 else ""
        if issue:
            lines.append(f"- {dim}: {score:.1f}{flag} — {issue}")
        else:
            lines.append(f"- {dim}: {score:.1f}{flag}")
    return "\n".join(lines)


def evaluate(query: str, response: str, *, llm: object) -> EvaluationResult:
    """Rubric-based scoring + regen recommendation.

    Truncates the response to 4000 chars before scoring — over that the
    Haiku context starts to dilute the rubric.
    """
    if llm is None:
        return EvaluationResult(
            score=0.0,
            rubric_notes="(evaluator skipped — no LLM backend wired)",
            regen_recommended=False,
        )

    try:
        raw = llm.complete(  # type: ignore[attr-defined]
            model="claude-haiku-4-5",
            system="You are the evaluator. Return one JSON object.",
            user=PROMPT_TEMPLATE.format(query=query, response=response[:4000]),
            max_tokens=800,
            temperature=0.0,
        )
        data = _parse(raw)
    except Exception as exc:  # noqa: BLE001
        return EvaluationResult(
            score=0.0,
            rubric_notes=f"(evaluator failure: {exc})",
            regen_recommended=False,
        )

    scores: dict[str, float] = {}
    issues: dict[str, str] = {}
    for dim in DIMENSIONS:
        block = data.get(dim) or {}
        if isinstance(block, dict):
            scores[dim] = float(block.get("score") or 0.0)
            issues[dim] = str(block.get("issue") or "")
        else:
            # Flat schema fallback: {"clarity": 8, ...}
            scores[dim] = float(block or 0.0)
            issues[dim] = ""

    total = _weighted_score(scores)
    return EvaluationResult(
        score=round(total, 2),
        rubric_notes=_format_notes(scores, issues),
        regen_recommended=total < REGEN_THRESHOLD,
    )
