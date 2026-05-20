# pytest

**Package:** `pytest`  •  **Version pin:** `>=8.0`  •  **Extras group:** `m3xa-core[dev]`  •  **Role:** Test runner

## What it does

The test runner. Runs everything under `tests/` — assembler tests, router parser tests, pipeline integration tests, and the BODY.md sync check.

## Where it's used in m3xa-core

- `tests/*.py` — all test modules.
- `pyproject.toml` `[tool.pytest.ini_options]` — sets `testpaths = ["tests"]`, `asyncio_mode = "auto"`.

## Why we picked it

The default for Python testing. Fixtures, parametrize, and discovery work as expected. No reason to use anything else.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| `unittest` | More boilerplate, no parametrize, worse failure output. |
| `nose2` | Maintenance is thin. Most projects have moved off. |

## How to swap it out

Don't. If you have a reason, the test files use only pytest idioms that translate easily, but you'd lose `pytest-asyncio` integration.

## Links

- Homepage: <https://docs.pytest.org>
- GitHub: <https://github.com/pytest-dev/pytest>
- Last verified: 2026-05-19
