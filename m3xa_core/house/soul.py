"""Soul — identity + analytical voice + refusal rules.

Loads from soul_modules/. A soul module is a markdown file with YAML
frontmatter declaring its triggers; the body is the analytical lens the
synthesizer reads.

Read by: the synthesizer (Actor 5).
Written by: humans, or the soul_amendment_engine WITH human approval.
"""
from __future__ import annotations

from pathlib import Path


def load_kernel(soul_dir: Path) -> str:
    """Load the always-on identity kernel. Skeleton."""
    raise NotImplementedError


def load_module(name: str, *, soul_dir: Path) -> str:
    """Load one soul module by name. Skeleton."""
    raise NotImplementedError
