"""m3xa-core — a didactic reference for the House pattern.

Public API surface. What's exported here is the stable contract; internal
modules can move without warning. See BODY.md for the live infrastructure
map.
"""
from m3xa_core.pipeline import Pipeline
from m3xa_core.schemas import (
    AgentContext,
    ClassifierOutput,
    EvaluationResult,
    PipelineResult,
    RetrievedDoc,
    RoutingDecision,
    SynthesizerInput,
)

__version__ = "0.1.0"

__all__ = [
    "Pipeline",
    "ClassifierOutput",
    "RoutingDecision",
    "AgentContext",
    "RetrievedDoc",
    "SynthesizerInput",
    "EvaluationResult",
    "PipelineResult",
]
