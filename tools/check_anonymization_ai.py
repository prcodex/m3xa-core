#!/usr/bin/env python3
"""AI-based anonymization check — uses Claude to judge whether a file is publication-safe.

Alternative to tools/check_anonymization.py (hash-based blocklist):

  tools/check_anonymization.py        — fast, deterministic, catches known
                                        tokens. Pre-commit + CI default.
  tools/check_anonymization_ai.py     — slower (~$0.02/run), broader, catches
                                        indirect references and novel mentions
                                        the hash blocklist would miss.

When to use which:
  - Routine pre-commit/CI:  hash check (no API call, no false positives from substrings)
  - Pre-publication gate:   AI check (catches what the blocklist doesn't know to look for)
  - Both, belt + suspenders, for high-stakes publications

The AI check is what the m3xa-core README's "self-knowledge layer" section
suggests as the second layer. See concepts/source_tiering.md for the rationale.

Usage:
  python tools/check_anonymization_ai.py <file>
  python tools/check_anonymization_ai.py <file> --model claude-sonnet-4-6
  python tools/check_anonymization_ai.py <file> --json    # machine-readable output

Exit codes:
  0 — clean
  1 — findings (real-name leaks detected)
  2 — API error / config error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are an anonymization auditor for a public, didactic reference repo
that describes a private intelligence-system architecture without
exposing its real source list.

The repo replaces real source names with anonymized aliases:
  - Banks (sell-side, commercial, regional):  Bank1..BankN, BankA..BankF
  - Independent analysts / experts:           Expert1..ExpertN
  - Boutique macro shops:                     Macro1..MacroN
  - Wire services (real-time newswires):      Wire1..WireN
  - State-aligned media outlets:              State1..StateN
  - Think tanks:                              ThinkTank1..ThinkTankN
  - Podcasts / YouTube channels:              Podcast1..PodcastN
  - Subject institutions:                     Inst1..InstN
  - Political figures (subjects of coverage): Pol1..PolN
  - Countries:                                CountryA..CountryZ, RegionX..RegionZ
  - Hosts / servers:                          RagHost, ScraperHub, Gateway
  - Telegram bots:                            @MainBot, @RegionalBot
  - Domains:                                  example.org variants

YOUR JOB: scan the provided document and identify any text that
references a REAL named entity in any of the forbidden categories
above. Catch:

  1. Direct named references — "Goldman Sachs", "Bloomberg",
     "Niall Ferguson", "Khamenei", etc.
  2. Indirect identifications — "the Wall Street firm founded in 1869",
     "the Iranian Supreme Leader", "the New York-based news terminal"
     that uniquely identify a real entity even without naming it.
  3. Identifying tickers, handles, URLs — "@DeItaone", "ft.com",
     a Bloomberg ticker that points at a specific named entity.

DO NOT flag:
  - The anonymized aliases themselves (Bank1, Expert1, Wire2, etc.) —
    those are CORRECT.
  - Generic role descriptors (central bank, finance ministry, hedge fund)
    that don't uniquely identify a real entity.
  - Public vendor/research org names cited as RESEARCH SOURCES
    (Anthropic, Cohere, AWS, Amazon, Jina AI, AI21, MTEB, FinanceBench,
    etc.) — these are research citations, not financial-intel sources.
  - The author's own project names (M3xA, M3xBr, M3xAI), their bot
    aliases (@MainBot, @M3xabot), or their own infrastructure (R6G,
    if it appears) — these are the author's brand.
  - Programming languages, libraries, model IDs (cohere.embed-v4,
    voyage-3-large, claude-haiku-4-5, etc.).

Output STRICT JSON only, no prose, no markdown fences:

{
  "clean": true | false,
  "findings": [
    {
      "line": <int, 1-indexed>,
      "text": "<the offending substring>",
      "category": "bank" | "expert" | "wire" | "outlet" | "podcast" | "think_tank" | "political_figure" | "other",
      "reason": "<one sentence on why this is a leak>"
    },
    ...
  ],
  "summary": "<one sentence summary of the audit>"
}

If clean, return {"clean": true, "findings": [], "summary": "..."}.

Be precise. False positives waste time; false negatives compromise the
publication. When in doubt, flag and let the human decide.
"""


def build_user_prompt(path: Path, text: str) -> str:
    numbered = "\n".join(f"{i+1:>5d}  {line}" for i, line in enumerate(text.splitlines()))
    return (
        f"File: {path}\n"
        f"Length: {len(text)} chars, {text.count(chr(10)) + 1} lines.\n\n"
        f"Document (line-numbered for findings.line):\n\n{numbered}\n"
    )


def run_check(path: Path, *, model: str) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package required. pip install anthropic", file=sys.stderr)
        sys.exit(2)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(2)

    if not path.exists():
        print(f"ERROR: {path} does not exist.", file=sys.stderr)
        sys.exit(2)

    text = path.read_text(encoding="utf-8")

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(path, text)}],
    )

    raw = "".join(b.text for b in response.content if hasattr(b, "text")).strip()

    # Tolerate light Markdown fencing the model may emit despite the instruction.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print("ERROR: model returned non-JSON output:", file=sys.stderr)
        print(raw[:1000], file=sys.stderr)
        print(f"\nJSON error: {e}", file=sys.stderr)
        sys.exit(2)


def print_human(verdict: dict, path: Path) -> None:
    if verdict.get("clean"):
        print(f"✓ {path}: clean ({verdict.get('summary', '')})")
        return

    print(f"✗ {path}: anonymization issues found")
    print(f"  {verdict.get('summary', '')}")
    print()
    for f in verdict.get("findings", []):
        line = f.get("line", "?")
        cat = f.get("category", "?")
        text = f.get("text", "")
        reason = f.get("reason", "")
        print(f"  line {line}  [{cat}]  {text!r}")
        print(f"             → {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-based anonymization audit using Claude."
    )
    parser.add_argument("file", type=Path, help="Markdown or text file to audit")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model id (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON verdict to stdout instead of human-readable",
    )
    args = parser.parse_args()

    verdict = run_check(args.file, model=args.model)

    if args.json:
        json.dump(verdict, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_human(verdict, args.file)

    return 0 if verdict.get("clean") else 1


if __name__ == "__main__":
    sys.exit(main())
