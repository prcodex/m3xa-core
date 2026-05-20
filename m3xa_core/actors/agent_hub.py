"""Actor 3 — Agent Hub. Fires zero or more data agents in parallel.

Each agent decides whether to fire based on ClassifierOutput. Failed
agents return None — never raise. The synthesizer treats agent outputs
as supplementary context, not as ground truth.
"""
from __future__ import annotations

from m3xa_core.schemas import AgentContext, ClassifierOutput


class AgentHub:
    """Registry of data agents."""

    def __init__(self, agents: list[object] | None = None) -> None:
        self.agents = agents or []

    def register(self, agent: object) -> None:
        self.agents.append(agent)

    def fire(self, classifier_output: ClassifierOutput) -> list[AgentContext]:
        """Run all registered agents in parallel; collect non-None outputs.

        Skeleton.
        """
        raise NotImplementedError
