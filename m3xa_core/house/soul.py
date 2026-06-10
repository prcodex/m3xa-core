"""Soul — identity + analytical voice + refusal rules.

Loads from soul_modules/. A soul module is a markdown file with YAML
frontmatter declaring its triggers; the body is the analytical lens the
synthesizer reads.

Read by: the synthesizer (Actor 5).
Written by: humans, or the soul_amendment_engine WITH human approval.
"""
from __future__ import annotations

import re
from pathlib import Path

KERNEL_NAME = "m3xa_kernel"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def _read_module(path: Path) -> str:
    """Read a markdown file and strip its YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    return (m.group(2) if m else text).strip()


def load_kernel(soul_dir: Path) -> str:
    """Load the always-on identity kernel.

    The kernel file may live under either `expertises/m3xa_kernel.md`
    (the canonical home, since it's an expertise that is always loaded)
    or `soul_modules/m3xa_kernel.md`. Tries both, then returns "" if
    neither exists.
    """
    for candidate in (
        soul_dir / f"{KERNEL_NAME}.md",
        soul_dir.parent / "expertises" / f"{KERNEL_NAME}.md",
    ):
        if candidate.exists():
            return _read_module(candidate)
    return ""


def load_module(name: str, *, soul_dir: Path) -> str:
    """Load one soul module by name. Returns "" if missing.

    Names are slugs (e.g. `regional_voice`, `crisis_mode`) — the file is
    `soul_dir / f"{name}.md"`. Missing modules return empty so the
    synthesizer can degrade gracefully.
    """
    path = soul_dir / f"{name}.md"
    if not path.exists():
        return ""
    return _read_module(path)
