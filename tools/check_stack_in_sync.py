#!/usr/bin/env python3
"""Fail if any pyproject dependency is missing a doc under docs/stack/.

Every external package m3xa-core depends on must have a dedicated
`docs/stack/<name>.md` file. CI enforces this so the stack registry
never drifts. See `docs/stack/README.md` for the convention.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
STACK_DIR = REPO / "docs" / "stack"


def _normalize(pkg: str) -> str:
    return pkg.lower().replace("_", "-")


def collect_deps() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    proj = data.get("project", {})
    raw: list[str] = list(proj.get("dependencies", []))
    for _name, extras_deps in (proj.get("optional-dependencies") or {}).items():
        raw.extend(extras_deps)

    project_name = _normalize(str(proj.get("name", "")))
    names: list[str] = []
    for dep in raw:
        pkg = re.split(r"[<>=!~\s\[]", dep, maxsplit=1)[0].strip()
        if not pkg:
            continue
        norm = _normalize(pkg)
        if norm == project_name:
            continue
        if norm not in names:
            names.append(norm)
    return sorted(names)


def find_missing(deps: list[str]) -> list[str]:
    return [d for d in deps if not (STACK_DIR / f"{d}.md").exists()]


def main() -> int:
    if not PYPROJECT.exists():
        print(f"ERROR: {PYPROJECT} not found", file=sys.stderr)
        return 2
    if not STACK_DIR.exists():
        print(f"ERROR: {STACK_DIR} does not exist", file=sys.stderr)
        return 2

    deps = collect_deps()
    missing = find_missing(deps)

    if missing:
        print("Stack docs out of sync with pyproject.toml.", file=sys.stderr)
        print("", file=sys.stderr)
        print("The following dependencies are missing a doc under docs/stack/:", file=sys.stderr)
        for d in missing:
            print(f"  - {d}  (expected at docs/stack/{d}.md)", file=sys.stderr)
        print("", file=sys.stderr)
        print("Fix: create the file using docs/stack/anthropic.md as a template.", file=sys.stderr)
        return 1

    print(f"Stack docs in sync ({len(deps)} dependencies, all documented).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
