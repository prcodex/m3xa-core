# PyYAML

**Package:** `pyyaml`  •  **Version pin:** `>=6.0`  •  **Role:** Parse expertise frontmatter

## What it does

Reads the YAML frontmatter at the top of every `expertises/*.md` file (`name`, `tokens_estimate`, `triggers`, `not_for`, …). The assembler uses the parsed dict to validate that the file is well-formed before adding it to the synthesizer's system prompt.

## Where it's used in m3xa-core

- `m3xa_core/actors/assembler.py` — `yaml.safe_load()` on the frontmatter block between the two `---` lines.
- `config/retrieval_scoring.yaml` is also read here (numeric weights for ranking).

## Why we picked it

The standard. No real alternative for "read a small YAML file in a CLI." We use `safe_load` exclusively — no full-loader code paths.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `ruamel.yaml` | Better for round-tripping with comments preserved. We never write YAML, only read it. |
| Skip YAML, use TOML | Frontmatter is conventionally YAML in markdown ecosystems. Don't fight the convention. |

## How to swap it out

If you want comment preservation when programmatically editing expertise frontmatter, swap to `ruamel.yaml`. Otherwise leave it.

## Links

- Homepage: <https://pyyaml.org>
- GitHub: <https://github.com/yaml/pyyaml>
- Last verified: 2026-05-19
