"""self_evaluator — six-check structural audit per response.

Runs alongside Actor 7. Where the evaluator scores user-facing quality
(editorial rubric), the self_evaluator runs six structural checks:

1. Source attribution — every analytical claim points at a retrieved doc
2. Recency violation — citations match the user's implicit time window
3. Refusal misfire — should-have-refused / shouldn't-have-refused
4. Format drift — output schema matches what the soul module promised
5. Entity hallucination — named entities exist in the retrieved corpus
6. Confidence calibration — hedging proportional to retrieval coverage

Writes a JSONL log under .m3xa/self_eval/YYYY-MM-DD.jsonl. Failures fan
out to health_caveats_writer (structural) and soul_amendment_engine
(recurring patterns).
"""
from __future__ import annotations


def audit_response(*, query: str, response: str, retrieved: list[dict]) -> dict:
    """Run six checks, return per-check pass/fail + diagnostic notes.

    Skeleton.
    """
    raise NotImplementedError
