"""soul_amendment_engine — patterns become proposed soul edits, gated by #approve.

Reads self_evaluator output over a moving window. When the same expertise
hits the same structural failure >= 3 times, drafts an amendment to the
relevant soul module.

The amendment is NEVER auto-applied. It lands in
.m3xa/proposed_amendments/<id>.md and waits for a human #approve.

This is the most consequential component in the loop — Soul edits change
every future response. See concepts/soul_amendment_engine.md.
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

SELF_EVAL_ROOT = Path.home() / ".m3xa" / "self_eval"
PROPOSED_ROOT = Path.home() / ".m3xa" / "proposed_amendments"
APPLIED_ROOT = Path.home() / ".m3xa" / "applied_amendments"
SOUL_ROOT = Path.home() / ".m3xa" / "soul_modules"

PATTERN_THRESHOLD = 3   # n failures of the same shape before a draft fires
WINDOW_HOURS = 48       # look this far back in self_eval logs


def _iter_recent_evals(window_hours: int = WINDOW_HOURS, root: Path | None = None) -> list[dict]:
    """Read self_evaluator JSONL within the moving window."""
    out: list[dict] = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)
    root = root or SELF_EVAL_ROOT
    if not root.exists():
        return out
    for log_file in sorted(root.glob("*.jsonl")):
        try:
            stem_date = datetime.strptime(log_file.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if stem_date < cutoff - timedelta(days=1):
            continue
        for line in log_file.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def scan_for_patterns(*, window_hours: int = WINDOW_HOURS) -> list[dict]:
    """Detect recurring structural failures.

    A pattern is `(check_name, note_signature)` repeated >= PATTERN_THRESHOLD
    times in the window. The note is normalized to its first 40 chars to
    cluster "5 cites for 12 paragraphs" with "4 cites for 11 paragraphs".
    """
    evals = _iter_recent_evals(window_hours)
    bucket: Counter[tuple[str, str]] = Counter()
    for entry in evals:
        for check in entry.get("checks", []):
            if check.get("passed"):
                continue
            note_sig = (check.get("note") or "")[:40]
            bucket[(check.get("name", "?"), note_sig)] += 1

    patterns: list[dict] = []
    for (check_name, note_sig), count in bucket.items():
        if count >= PATTERN_THRESHOLD:
            patterns.append(
                {
                    "check": check_name,
                    "note_signature": note_sig,
                    "count": count,
                    "window_hours": window_hours,
                }
            )
    return patterns


def draft_amendment(pattern: dict) -> str:
    """Turn a pattern into a proposed soul-amendment markdown file.

    Writes to PROPOSED_ROOT and returns the file path. The body is a
    starter — the human reviewer is expected to tighten it before #approve.
    """
    amendment_id = uuid.uuid4().hex[:8]
    PROPOSED_ROOT.mkdir(parents=True, exist_ok=True)
    path = PROPOSED_ROOT / f"{amendment_id}.md"

    suggested_module = {
        "source_attribution": "m3xa_kernel.md (citation discipline)",
        "recency": "m3xa_kernel.md (recency hedging)",
        "refusal_misfire": "m3xa_kernel.md (refusal rules)",
        "format_drift": "macro_lens.md (output schema)",
        "entity_hallucination": "m3xa_kernel.md (citation discipline)",
        "confidence_calibration": "m3xa_kernel.md (hedging)",
    }.get(pattern["check"], "m3xa_kernel.md")

    path.write_text(
        f"""---
amendment_id: {amendment_id}
proposed_at: {datetime.now(tz=timezone.utc).isoformat()}
target_module: {suggested_module}
pattern_check: {pattern["check"]}
pattern_count: {pattern["count"]}
status: proposed
---

# Proposed amendment {amendment_id}

The self_evaluator flagged `{pattern["check"]}` failures
{pattern["count"]} times in the last {pattern["window_hours"]}h with the
signature `{pattern["note_signature"]}`.

## Suggested edit (starter — tighten before approve)

Add to `{suggested_module}`:

> When [trigger condition], the analyst must [behavior].

## Approval

Reply `#approve {amendment_id}` to apply, `#reject {amendment_id}` to dismiss.
""",
        encoding="utf-8",
    )
    return str(path)


def apply_amendment(amendment_id: str, *, approved_by: str) -> Path | None:
    """Move a proposed amendment to APPLIED_ROOT and stamp the approver.

    Idempotent: returns the applied-path even if already applied. Returns
    None if the proposal does not exist.
    """
    proposed = PROPOSED_ROOT / f"{amendment_id}.md"
    if not proposed.exists():
        return None
    APPLIED_ROOT.mkdir(parents=True, exist_ok=True)
    applied = APPLIED_ROOT / f"{amendment_id}.md"
    text = proposed.read_text(encoding="utf-8")
    stamp = f"\n\n---\napplied_at: {datetime.now(tz=timezone.utc).isoformat()}\napproved_by: {approved_by}\n"
    applied.write_text(text + stamp, encoding="utf-8")
    proposed.unlink(missing_ok=True)
    return applied
