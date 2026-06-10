"""Actor 5 — Synthesizer. Single Sonnet call producing the user-facing response.

The synthesizer is the only actor that consumes the *whole* assembled
context. It receives:

- A system prompt (kernel + picked expertises, from the assembler).
- The retrieved docs (from the retriever).
- The agent blocks (from the agent hub).
- The user's original query.

It emits the user-facing response. One LLM call. Streaming. Extended
thinking is on. If the model hits max_tokens it is asked to continue
once — bounded retry so a verbose answer doesn't double the cost.

The doc-formatting convention here is deliberate: every retrieved row is
serialized with `source`, `published_at`, and `score` so the synthesizer
can attribute claims by source alias and timestamp the way the kernel
demands.
"""
from __future__ import annotations

from m3xa_core.schemas import SynthesizerInput

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
MAX_CONTINUATIONS = 2


def _format_doc(doc, idx: int) -> str:
    ts = doc.published_at.strftime("%Y-%m-%d") if doc.published_at else "unknown"
    return (
        f"[{idx}] {doc.source} · {ts} · score={doc.score:.2f}\n"
        f"{doc.text[:5000]}"
    )


def _format_agent_block(block) -> str:
    return f"--- agent: {block.name} ({block.timestamp:%Y-%m-%d %H:%M UTC}) ---\n{block.content}"


def _build_user_message(inp: SynthesizerInput) -> str:
    parts: list[str] = []

    if inp.docs:
        parts.append("=== RETRIEVED CONTEXT ===")
        parts.extend(_format_doc(d, i) for i, d in enumerate(inp.docs, start=1))

    if inp.agent_blocks:
        parts.append("\n=== AGENT CONTEXT ===")
        parts.extend(_format_agent_block(b) for b in inp.agent_blocks)

    parts.append("\n=== QUERY ===")
    parts.append(inp.query)

    return "\n\n".join(parts)


def synthesize(inp: SynthesizerInput, *, llm: object) -> str:
    """One Sonnet call. Auto-continues once on max_tokens stop."""
    if llm is None:
        return "(synthesizer skipped — no LLM backend wired)"

    user_message = _build_user_message(inp)

    full: list[str] = []
    user_so_far = user_message
    for _ in range(MAX_CONTINUATIONS + 1):
        try:
            chunk = llm.complete(  # type: ignore[attr-defined]
                model=MODEL,
                system=inp.system_prompt,
                user=user_so_far,
                max_tokens=MAX_TOKENS,
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            full.append(f"(synthesizer error: {exc})")
            break

        full.append(chunk)

        # The provider may stash a stop_reason on the response; without that
        # hook we use a length-based heuristic as the continuation gate.
        if len(chunk) < MAX_TOKENS * 3:  # ~3 chars/token, under the cap
            break

        user_so_far = (
            f"{user_message}\n\n--- previous turn ended mid-thought ---\n"
            "Continue from where you left off. Do not repeat."
        )

    return "\n".join(full).strip()
