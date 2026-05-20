"""Actor 5 — Synthesizer. Single Sonnet call producing the user-facing response."""
from __future__ import annotations

from m3xa_core.schemas import SynthesizerInput


def synthesize(inp: SynthesizerInput, *, llm: object) -> str:
    """Assemble system prompt + retrieved docs + agent blocks; one Sonnet call.

    Skeleton.
    """
    raise NotImplementedError
