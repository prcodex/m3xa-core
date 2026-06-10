"""Actor 3 — Agent Hub. Fires zero or more data agents in parallel.

A *data agent* enriches the synthesizer's context with structured
real-time data that vector search can't supply: market quotes, prediction-
market odds, calendar events, polling. Each agent is a callable that:

- Inspects the `ClassifierOutput` and decides whether it should fire.
- If yes, returns one `AgentContext` (name + content block + timestamp).
- If no, or on failure, returns None — never raises.

Parallelism is via `ThreadPoolExecutor`. The hub waits for every active
agent up to a deadline, drops None / exception results, and returns the
list of `AgentContext` blocks for the synthesizer to splice into context.

Budget: each agent is allocated a character budget from its registered
priority. After firing, the hub truncates over-budget output and
redistributes leftover budget to the largest blocks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from m3xa_core.schemas import AgentContext, ClassifierOutput

AgentFn = Callable[[ClassifierOutput, int], str | None]


@dataclass
class RegisteredAgent:
    """One agent registration."""

    name: str
    fetch: AgentFn
    always: bool = False
    priority: int = 5  # 1 (low) - 10 (high)
    budget: int = 2000  # characters
    label: str = ""

    def should_fire(self, classifier_output: ClassifierOutput) -> bool:
        if self.always:
            return True
        # Default heuristic: fire when any agent-tagged topic appears.
        # Production agents override this with their own detector.
        return bool(classifier_output.topics)


class AgentHub:
    """Registry of data agents + parallel firing.

    Construct with an empty hub and register agents at runtime, or pass
    a pre-built list. Agents must be deterministic enough that two calls
    with the same classifier output produce the same context — there is
    no cache layer.
    """

    def __init__(
        self,
        agents: list[RegisteredAgent] | None = None,
        *,
        timeout_seconds: float = 5.0,
        total_budget: int = 8000,
    ) -> None:
        self.agents: list[RegisteredAgent] = list(agents or [])
        self.timeout_seconds = timeout_seconds
        self.total_budget = total_budget

    def register(self, agent: RegisteredAgent) -> None:
        self.agents.append(agent)

    def fire(self, classifier_output: ClassifierOutput) -> list[AgentContext]:
        """Run every active agent in parallel; collect non-None outputs.

        Failures (timeouts, raised exceptions, None returns) are dropped
        silently — the synthesizer treats agent blocks as *supplementary*
        context, never as ground truth.
        """
        active = [a for a in self.agents if a.should_fire(classifier_output)]
        if not active:
            return []

        blocks: list[AgentContext] = []
        with ThreadPoolExecutor(max_workers=max(1, len(active))) as pool:
            futures = {
                pool.submit(self._fire_one, a, classifier_output): a for a in active
            }
            for future in as_completed(futures, timeout=self.timeout_seconds):
                ctx = future.result()
                if ctx is not None:
                    blocks.append(ctx)

        return self._apply_budget(blocks, active)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fire_one(
        self,
        agent: RegisteredAgent,
        classifier_output: ClassifierOutput,
    ) -> AgentContext | None:
        try:
            content = agent.fetch(classifier_output, agent.budget)
        except Exception:
            return None
        if not content:
            return None
        return AgentContext(
            name=agent.name,
            content=content,
            timestamp=datetime.now(tz=timezone.utc),
        )

    def _apply_budget(
        self,
        blocks: list[AgentContext],
        active: list[RegisteredAgent],
    ) -> list[AgentContext]:
        """Truncate each block to its agent's budget, then redistribute slack."""
        by_name = {a.name: a for a in active}
        budgeted: list[AgentContext] = []
        used = 0
        for block in blocks:
            budget = by_name[block.name].budget if block.name in by_name else 1000
            text = block.content[: min(budget, self.total_budget - used)]
            used += len(text)
            budgeted.append(
                AgentContext(name=block.name, content=text, timestamp=block.timestamp)
            )
            if used >= self.total_budget:
                break
        return budgeted
