"""Pipeline-edge contracts.

Every actor accepts and returns one of these types. Treat the shapes as a
published API — downstream consumers depend on them.

Keep them small. The router output is the most-depended-on; changing it
requires touching every actor downstream.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClassifierOutput(BaseModel):
    """Actor 1 — output of the classifier (Haiku)."""

    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    intent: str = "question"
    time_window_hours: int | None = None
    confidence: float = 0.0


class RoutingDecision(BaseModel):
    """Actor 1.5 — output of the router. Hard contract; do not break."""

    expertises: list[str]
    confidence: float
    rationale: str


class AgentContext(BaseModel):
    """Actor 3 — output of one agent in the agent hub.

    Agent hub fires zero or more agents in parallel; each returns one
    AgentContext block that the synthesizer concatenates.
    """

    name: str
    content: str
    timestamp: datetime


class RetrievedDoc(BaseModel):
    """Actor 4 — one row from the retriever."""

    id: str
    text: str
    source: str  # aliased — never a real name
    published_at: datetime | None = None
    score: float = 0.0
    domain: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SynthesizerInput(BaseModel):
    """Actor 5 — assembled input to the synthesizer (Sonnet)."""

    query: str
    system_prompt: str
    docs: list[RetrievedDoc]
    agent_blocks: list[AgentContext]
    estimated_system_tokens: int


class EvaluationResult(BaseModel):
    """Actor 7 — evaluator output. User-facing quality score."""

    score: float
    rubric_notes: str
    regen_recommended: bool = False


class PipelineResult(BaseModel):
    """Whole-pipeline output. What `Pipeline.run(query)` returns."""

    query: str
    response: str
    score: float
    routing_decision: RoutingDecision
    retrieved: list[RetrievedDoc]
    estimated_system_tokens: int
    evaluation: EvaluationResult
