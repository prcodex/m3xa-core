"""Actor 2 — Expertise Assembler. Concatenates picked expertises into a system prompt."""
from __future__ import annotations

from pathlib import Path

from m3xa_core.schemas import RoutingDecision


def assemble(routing: RoutingDecision, *, expertises_dir: Path) -> tuple[str, int]:
    """Pure file ops. No LLM call.

    Returns (system_prompt, estimated_tokens). The kernel and scope filter
    are always loaded; the router's picks are appended in routing order.
    Skeleton.
    """
    raise NotImplementedError
