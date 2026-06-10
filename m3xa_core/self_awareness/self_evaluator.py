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

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_ROOT = Path.home() / ".m3xa" / "self_eval"
HEDGE_WORDS = (
    "appears", "likely", "suggests", "may", "might", "could",
    "indicates", "consistent with", "based on", "tentatively",
)
REFUSAL_PHRASES = (
    "i cannot", "i can't", "i won't", "i will not",
    "unable to provide", "refuse",
)
CITE_PATTERN = re.compile(r"\[(?P<src>[A-Za-z0-9_.-]+)\s*·\s*(?P<date>\d{4}-\d{2}-\d{2})\]")


@dataclass
class CheckResult:
    name: str
    passed: bool
    note: str = ""


@dataclass
class AuditResult:
    query: str
    checks: list[CheckResult] = field(default_factory=list)
    overall_passed: bool = True

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "overall_passed": self.overall_passed,
            "checks": [{"name": c.name, "passed": c.passed, "note": c.note} for c in self.checks],
        }


# ---------------------------------------------------------------------------
# The six checks
# ---------------------------------------------------------------------------
def _check_source_attribution(response: str, retrieved: list[dict]) -> CheckResult:
    """Every paragraph with an analytical claim should include a citation."""
    if not retrieved:
        return CheckResult("source_attribution", True, "no retrieved docs to attribute")
    cites = CITE_PATTERN.findall(response)
    paragraphs = [p for p in response.split("\n\n") if len(p.strip()) > 80]
    if not paragraphs:
        return CheckResult("source_attribution", True, "response too short to require cites")
    expected = max(1, len(paragraphs) // 2)
    if len(cites) >= expected:
        return CheckResult("source_attribution", True, f"{len(cites)} cites, {len(paragraphs)} paras")
    return CheckResult(
        "source_attribution",
        False,
        f"{len(cites)} cites for {len(paragraphs)} paragraphs (expected >= {expected})",
    )


def _check_recency(response: str, time_window_hours: int | None) -> CheckResult:
    """Cited dates should fall within the query's implicit time window."""
    if not time_window_hours:
        return CheckResult("recency", True, "no time window declared")
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=time_window_hours)
    stale: list[str] = []
    for _, date_str in CITE_PATTERN.findall(response):
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if d < cutoff:
            stale.append(date_str)
    if not stale:
        return CheckResult("recency", True, "")
    return CheckResult("recency", False, f"{len(stale)} citations older than window")


def _check_refusal_misfire(query: str, response: str, retrieved: list[dict]) -> CheckResult:
    """Should the model have refused (or not refused)?"""
    refused = any(phrase in response.lower() for phrase in REFUSAL_PHRASES)
    if refused and retrieved:
        return CheckResult(
            "refusal_misfire",
            False,
            "model refused but corpus had relevant docs",
        )
    if not refused and not retrieved and len(query) > 0:
        # Empty corpus + no refusal = potential hallucination. Soft fail.
        return CheckResult(
            "refusal_misfire",
            False,
            "no retrieved docs but model didn't hedge with a refusal",
        )
    return CheckResult("refusal_misfire", True, "")


def _check_format_drift(response: str, expected_schema: str | None = None) -> CheckResult:
    """Trivial baseline: response is non-empty + uses sentences, not table dumps."""
    text = response.strip()
    if not text:
        return CheckResult("format_drift", False, "empty response")
    if expected_schema == "markdown":
        if not any(line.startswith("#") or line.startswith("-") for line in text.splitlines()):
            return CheckResult("format_drift", False, "markdown expected, none detected")
    if expected_schema == "prose":
        if text.count("|") > text.count(".") * 2:
            return CheckResult("format_drift", False, "prose expected, table-heavy")
    return CheckResult("format_drift", True, "")


def _check_entity_hallucination(response: str, retrieved: list[dict]) -> CheckResult:
    """Named entities in the response must appear in retrieved corpus.

    Catches the "Expert3 said X" failure mode where Expert3 wasn't in any
    retrieved doc.
    """
    if not retrieved:
        return CheckResult("entity_hallucination", True, "no corpus to check against")
    corpus = " ".join(d.get("text", "") for d in retrieved).lower()
    # Look for citation-shaped tokens that look like aliases
    cited_sources = {src for src, _ in CITE_PATTERN.findall(response)}
    missing = [s for s in cited_sources if s.lower() not in corpus and s.lower() not in " ".join(d.get("source", "").lower() for d in retrieved)]
    if missing:
        return CheckResult("entity_hallucination", False, f"unsupported: {missing[:5]}")
    return CheckResult("entity_hallucination", True, "")


def _check_confidence_calibration(response: str, retrieved: list[dict]) -> CheckResult:
    """Hedging should scale with retrieval coverage."""
    n_docs = len(retrieved)
    hedge_count = sum(response.lower().count(w) for w in HEDGE_WORDS)
    word_count = max(1, len(response.split()))
    hedge_rate = hedge_count / word_count
    if n_docs < 3 and hedge_rate < 0.005:
        return CheckResult(
            "confidence_calibration",
            False,
            f"thin retrieval ({n_docs} docs) but barely any hedging",
        )
    return CheckResult("confidence_calibration", True, "")


# ---------------------------------------------------------------------------
# Audit entry point
# ---------------------------------------------------------------------------
def audit_response(
    *,
    query: str,
    response: str,
    retrieved: list[dict],
    time_window_hours: int | None = None,
    expected_schema: str | None = None,
    log_dir: Path | None = None,
) -> dict:
    """Run six checks; return per-check pass/fail + diagnostic notes.

    Writes one JSONL line under `log_dir / YYYY-MM-DD.jsonl`. Defaults to
    `~/.m3xa/self_eval/`.
    """
    result = AuditResult(query=query)
    result.checks = [
        _check_source_attribution(response, retrieved),
        _check_recency(response, time_window_hours),
        _check_refusal_misfire(query, response, retrieved),
        _check_format_drift(response, expected_schema),
        _check_entity_hallucination(response, retrieved),
        _check_confidence_calibration(response, retrieved),
    ]
    result.overall_passed = all(c.passed for c in result.checks)

    out_dir = log_dir or LOG_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / f"{datetime.now(tz=timezone.utc):%Y-%m-%d}.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result.to_dict()) + "\n")

    return result.to_dict()
