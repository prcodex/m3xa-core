# Tool stack registry

Every external package the repo depends on has a dedicated `.md` doc in this directory. CI enforces it via `tools/check_stack_in_sync.py` — adding a new dependency to `pyproject.toml` without a doc here fails the build.

## Why

When Cursor / Claude Code / Copilot read this repo and see `from anthropic import Anthropic` or `import lancedb`, they need a fast way to know:
- **what the tool does** in the context of m3xa-core
- **why we picked it** over alternatives
- **how it's used** here (which actor/backend, which contract)
- **how to swap it** if needed

The README on the tool's own site is too generic. The docs here are repo-specific.

## Convention

Every doc follows this template (no strict schema — sections may be elided when truly N/A, but the headers should match for searchability):

```markdown
# <Tool Name>

**Package:** `<pyproject name>`  •  **Version pin:** `>=X.Y`  •  **Role:** <one line>

## What it does
1-2 sentences. Plain English. No marketing.

## Where it's used in m3xa-core
- `m3xa_core/backends/<file>.py` — primary integration
- `<other usages, if any>`

## Why we picked it
The deciding factor(s). Performance, license, ecosystem fit, etc.

## Alternatives considered
| Alternative | Why we didn't pick it |
|---|---|
| X | Reason |

## How to swap it out
Concrete steps if someone forks and wants to replace it. Usually: implement the corresponding interface in `m3xa_core/backends/`.

## Links
- Homepage / Docs
- GitHub
- Last verified: YYYY-MM-DD
```

## Registry (kept in sync with `pyproject.toml`)

| Package | Required? | Role | Doc |
|---|---|---|---|
| anthropic | core | LLM (Sonnet, Haiku) | [`anthropic.md`](./anthropic.md) |
| voyageai | core | Embeddings (voyage-3-large) | [`voyageai.md`](./voyageai.md) |
| lancedb | core | Vector DB | [`lancedb.md`](./lancedb.md) |
| pyarrow | core | Arrow / Parquet backend for LanceDB | [`pyarrow.md`](./pyarrow.md) |
| pydantic | core | Schema validation | [`pydantic.md`](./pydantic.md) |
| pyyaml | core | Expertise frontmatter parsing | [`pyyaml.md`](./pyyaml.md) |
| typer | core | CLI framework | [`typer.md`](./typer.md) |
| rich | core | Terminal output | [`rich.md`](./rich.md) |
| python-dateutil | core | Date parsing | [`python-dateutil.md`](./python-dateutil.md) |
| httpx | core | HTTP client for scrapers | [`httpx.md`](./httpx.md) |
| feedparser | core | RSS / Atom parsing | [`feedparser.md`](./feedparser.md) |
| openai | extras: openai | Alternative LLM | [`openai.md`](./openai.md) |
| cohere | extras: cohere | Alternative embeddings | [`cohere.md`](./cohere.md) |
| yfinance | extras: markets | Market data | [`yfinance.md`](./yfinance.md) |
| pytest | extras: dev | Test runner | [`pytest.md`](./pytest.md) |
| pytest-asyncio | extras: dev | Async test support | [`pytest-asyncio.md`](./pytest-asyncio.md) |
| ruff | extras: dev | Linter / formatter | [`ruff.md`](./ruff.md) |
| mypy | extras: dev | Type checker | [`mypy.md`](./mypy.md) |

## Adding a new tool

```bash
# 1. Add to pyproject.toml
# 2. Scaffold the doc
cp docs/stack/anthropic.md docs/stack/<new-name>.md   # copy the most complete one as a template
$EDITOR docs/stack/<new-name>.md                       # fill in the details

# 3. Verify the check passes
python tools/check_stack_in_sync.py

# 4. Regenerate BODY.md (the stack table auto-updates)
python tools/regenerate_body.py

# 5. Commit
git add pyproject.toml docs/stack/<new-name>.md BODY.md
git commit -m "Add <new-name> to the stack"
```

If you skip step 2, CI fails. The check is intentionally noisy.
