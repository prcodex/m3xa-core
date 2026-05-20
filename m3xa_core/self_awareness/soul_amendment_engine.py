"""soul_amendment_engine — patterns become proposed soul edits, gated by #approve.

Reads self_evaluator output over a moving window. When the same expertise
hits the same structural failure ≥3 times, drafts an amendment to the
relevant soul module.

The amendment is NEVER auto-applied. It lands in
.m3xa/proposed_amendments/<id>.md and waits for a human #approve.

This is the most consequential component in the loop — Soul edits change
every future response. See concepts/soul_amendment_engine.md.
"""
from __future__ import annotations


def scan_for_patterns() -> list[dict]:
    """Detect recurring patterns in self_evaluator output. Skeleton."""
    raise NotImplementedError


def draft_amendment(pattern: dict) -> str:
    """Turn a pattern into a proposed soul amendment. Skeleton."""
    raise NotImplementedError


def apply_amendment(amendment_id: str, *, approved_by: str) -> None:
    """Apply an approved amendment. Logs who approved it. Skeleton."""
    raise NotImplementedError
