# Contributing to m3xa-core

This repo is now a **public reference of the live M3xA system** — production souls, real source list, real environment map, with credentials stripped. Contributions that improve clarity, add patterns, or fix mistakes are welcome.

**Do not commit credentials** — API keys, bot tokens, OAuth secrets, email passwords. The anonymization tooling under `tools/` is retained for credential leak detection (you can populate `.anonymization-blocklist.txt` locally with any token strings you want to fail the build on).

## Before you contribute

Read [`AGENTS.md`](AGENTS.md) and [`BODY.md`](BODY.md). They describe how the repo stays coherent — autogen sections, sync checks, anonymization enforcement.

## Setup

```bash
git clone https://github.com/prcodex/m3xa-core.git
cd m3xa-core
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,markets]"
pre-commit install
```

## The three checks every contribution must pass

```bash
python tools/regenerate_body.py          # 1. BODY.md in sync
python tools/check_stack_in_sync.py      # 2. every dep has a docs/stack/ doc
python tools/check_anonymization.py      # 3. no real source names
pytest tests/                            # 4. all tests green
```

Pre-commit runs the first three on every commit. CI re-runs all four on every PR.

### Optional pre-publication AI gate

For high-stakes publications (you're about to push a doc that lifts internal architecture into a public repo), also run:

```bash
python tools/check_anonymization_ai.py path/to/file.md     # needs ANTHROPIC_API_KEY
```

The hash-based `check_anonymization.py` catches *known* tokens; the AI check catches *indirect* identifications — "the Wall Street firm founded in 1869" still de-anonymizes a bank without naming it. Use both for high-stakes pushes, hash-only for routine commits. See `LESSONS.md` entry dated 2026-05-21 for the why.

## Adding a concept essay

Concept essays live in [`concepts/`](concepts/). They're the most valuable contribution — what makes the repo didactic.

A concept file is a markdown file with this frontmatter:

```markdown
---
name: <slug>
description: <one-line summary — used in the BODY.md autogen table>
type: concept
applies_to: m3xa-core
status: stub | draft | stable
---
```

Then sections explaining the *why* (more than the *what* — code is for what). Link liberally to the source files the concept describes, using GitHub blob URLs so the links work both in the repo and on rendered docs.

## Adding a scraper template

Add `m3xa_core/scrapers/<name>_template.py`. The conventions are in [`m3xa_core/scrapers/README.md`](m3xa_core/scrapers/README.md). The template must:

1. Use an **alias** for the source name (`Bank1`, `Expert1`, …) — never a real one.
2. Demonstrate the **idempotency** pattern (stable id → re-running is a no-op).
3. Set `has_vector=1.0` alongside `content_vector`.
4. Have a `run()` function that takes `embeddings` and `vector_db` as arguments — no global backend instantiation.

## Adding a dependency

Every external package must have a doc under [`docs/stack/`](docs/stack/). CI fails the build if you add to `pyproject.toml` without doing this.

1. Add the package to `[project.dependencies]` (or the right extras group) in `pyproject.toml`.
2. Scaffold the doc — copy the closest existing one:
   ```bash
   cp docs/stack/anthropic.md docs/stack/<new-name>.md
   $EDITOR docs/stack/<new-name>.md
   ```
3. Verify the check passes:
   ```bash
   python tools/check_stack_in_sync.py
   ```
4. Regenerate BODY.md:
   ```bash
   python tools/regenerate_body.py
   ```
5. Stage and commit `pyproject.toml`, the new doc, and the updated `BODY.md` together.

## Adding a self-awareness component

Each component is a small module under [`m3xa_core/self_awareness/`](m3xa_core/self_awareness/). Conventions:

- **One write path** — the component writes to exactly one artifact location.
- **No cross-writes** — other components read your artifacts but don't write into them.
- **Opt-in at runtime** — the pipeline runs fine when your component is disabled.

After adding the file, update [`concepts/self_awareness_loop.md`](concepts/self_awareness_loop.md) with one paragraph describing the component (or, if it's a major addition, a dedicated concept essay).

## What this repo is not

- **Not a place for real source names.** Banks, expert analysts, podcasts, wire services — never. The check is automated.
- **Not a place for live deployment configs.** Cron schedules, Telegram tokens, server hostnames — all anonymized to patterns.
- **Not a competitor to your private fork.** This is the *pattern*. Your private fork has the live system. Patches that flow upstream improve the pattern; patches that leak the system don't.

## License

By contributing, you agree your contribution is MIT-licensed (see [`LICENSE`](LICENSE)).
