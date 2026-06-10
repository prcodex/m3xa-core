"""Actor 2 — Expertise Assembler. Concatenates picked expertises into a system prompt.

Pure file ops. No LLM call. The assembler reads:

1. The **kernel** (always loaded) — identity, voice, citation discipline.
2. The expertises the router picked — appended in routing order.

Every block is separated by a `\\n\\n---\\n\\n` divider so the synthesizer
can see the structure. Tokens are estimated as `len(prompt) // 4` — the
standard 4-chars-per-token approximation, sufficient for budget checks.

Why pure file ops: the assembled prompt is deterministic given a routing
decision. That makes the pipeline cheap to debug: same routing -> same
prompt. The LLM only enters at synthesis.
"""
from __future__ import annotations

from pathlib import Path

from m3xa_core.schemas import RoutingDecision

KERNEL_NAME = "m3xa_kernel"
DIVIDER = "\n\n---\n\n"


def _read_module(name: str, expertises_dir: Path) -> str | None:
    """Read one expertise markdown by name. Returns None if not found.

    Strips YAML frontmatter — the synthesizer doesn't need the metadata.
    """
    path = expertises_dir / f"{name}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    return text.strip()


def _estimate_tokens(prompt: str) -> int:
    """4 chars per token is the standard rough approximation."""
    return max(1, len(prompt) // 4)


def assemble(routing: RoutingDecision, *, expertises_dir: Path) -> tuple[str, int]:
    """Build the system prompt from the routing decision.

    Returns (system_prompt, estimated_tokens). Order:

    1. Kernel (always)
    2. Each picked expertise in `routing.expertises` order

    Missing files are silently skipped — the router may reference an
    expertise that's not yet written, and the pipeline should still
    answer (just without that lens).
    """
    parts: list[str] = []

    kernel = _read_module(KERNEL_NAME, expertises_dir)
    if kernel is not None:
        parts.append(kernel)

    for name in routing.expertises:
        if name == KERNEL_NAME:
            continue
        block = _read_module(name, expertises_dir)
        if block is not None:
            parts.append(block)

    prompt = DIVIDER.join(parts) if parts else ""
    return prompt, _estimate_tokens(prompt)
