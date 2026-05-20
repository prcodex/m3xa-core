#!/usr/bin/env python3
"""Regenerate the AUTOGEN sections of BODY.md from the live codebase.

Reads:
  - m3xa_core/actors/*.py              (actor list)
  - m3xa_core/self_awareness/*.py      (self-awareness components)
  - m3xa_core/scrapers/*.py            (scraper templates)
  - expertises/*.md                    (expertise inventory + frontmatter)
  - concepts/*.md                      (didactic essays)
  - pyproject.toml                     (dependency list)
  - tests/*.py                         (test counts)
  - m3xa_core/__init__.py              (public API surface)
  - all source files                   (env-var grep)

Writes:
  - BODY.md                            (only between AUTOGEN markers)

Invoked by:
  - pre-commit hook (.pre-commit-config.yaml)
  - CI workflow (.github/workflows/body_in_sync.yml)
  - manually: `python tools/regenerate_body.py [--check]`

`--check` mode: exits 1 if BODY.md is out of sync (re-runs and diffs).
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BODY = REPO / "BODY.md"


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------
def _module_docstring(p: Path) -> str:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        return (ast.get_docstring(tree) or "").split("\n")[0]
    except Exception:
        return "(unable to parse)"


def gen_actors() -> str:
    actors_dir = REPO / "m3xa_core" / "actors"
    if not actors_dir.exists():
        return "_(no m3xa_core/actors/ directory)_"
    rows = ["| Actor | File | First-line docstring |", "|---|---|---|"]
    for p in sorted(actors_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        doc = _module_docstring(p)
        rows.append(
            f"| `{p.stem}` | [`m3xa_core/actors/{p.name}`](./m3xa_core/actors/{p.name}) | "
            f"{doc or '_(no docstring)_'} |"
        )
    return "\n".join(rows)


def gen_self_awareness() -> str:
    sa_dir = REPO / "m3xa_core" / "self_awareness"
    if not sa_dir.exists():
        return "_(no m3xa_core/self_awareness/ directory)_"
    rows = ["| Component | File | First-line docstring |", "|---|---|---|"]
    for p in sorted(sa_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        doc = _module_docstring(p)
        rows.append(
            f"| `{p.stem}` | [`m3xa_core/self_awareness/{p.name}`](./m3xa_core/self_awareness/{p.name}) | "
            f"{doc or '_(no docstring)_'} |"
        )
    return "\n".join(rows)


def gen_scrapers() -> str:
    sc_dir = REPO / "m3xa_core" / "scrapers"
    if not sc_dir.exists():
        return "_(no m3xa_core/scrapers/ directory)_"
    rows = ["| Template | File | First-line docstring |", "|---|---|---|"]
    for p in sorted(sc_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        doc = _module_docstring(p)
        rows.append(
            f"| `{p.stem}` | [`m3xa_core/scrapers/{p.name}`](./m3xa_core/scrapers/{p.name}) | "
            f"{doc or '_(no docstring)_'} |"
        )
    return "\n".join(rows)


def gen_expertises() -> str:
    exp_dir = REPO / "expertises"
    if not exp_dir.exists():
        return "_(no expertises/ directory)_"
    rows = ["| Expertise | File | Tokens (est) | Triggers |", "|---|---|---|---|"]
    for p in sorted(exp_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        name = fm.get("name") or p.stem
        tokens = fm.get("tokens_estimate") or "?"
        triggers = (fm.get("triggers") or "")[:80]
        rows.append(
            f"| {name} | [`expertises/{p.name}`](./expertises/{p.name}) | {tokens} | {triggers} |"
        )
    return "\n".join(rows)


def gen_concepts() -> str:
    c_dir = REPO / "concepts"
    if not c_dir.exists():
        return "_(no concepts/ directory)_"
    rows = ["| Concept | File | Status | Description |", "|---|---|---|---|"]
    for p in sorted(c_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        name = fm.get("name") or p.stem
        status = fm.get("status") or "stable"
        desc = (fm.get("description") or "")[:80]
        rows.append(
            f"| {name} | [`concepts/{p.name}`](./concepts/{p.name}) | {status} | {desc} |"
        )
    return "\n".join(rows)


def gen_stack() -> str:
    pyproject = REPO / "pyproject.toml"
    if not pyproject.exists():
        return "_(pyproject.toml not found)_"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps: list[str] = []
    proj = data.get("project", {})
    deps.extend(proj.get("dependencies", []))
    for extras_name, extras_deps in (proj.get("optional-dependencies") or {}).items():
        for d in extras_deps:
            deps.append(f"{d} _(extras: {extras_name})_")
    project_name = str(proj.get("name", "")).lower().replace("_", "-")
    rows = ["| Package | Role | Doc |", "|---|---|---|"]
    stack_dir = REPO / "docs" / "stack"
    for dep in sorted(deps):
        pkg_name = re.split(r"[<>=!~\s\[]", dep, maxsplit=1)[0].strip()
        if not pkg_name:
            continue
        norm = pkg_name.lower().replace("_", "-")
        if norm == project_name:
            continue
        doc_path = stack_dir / f"{norm}.md"
        if doc_path.exists():
            doc_link = f"[`docs/stack/{doc_path.name}`](./docs/stack/{doc_path.name})"
        else:
            doc_link = "**MISSING — register via `docs/stack/`**"
        rows.append(f"| `{dep}` | _(see doc)_ | {doc_link} |")
    return "\n".join(rows)


def gen_env_vars() -> str:
    matches: set[str] = set()
    pat = re.compile(
        r"os\.(?:getenv|environ\.get|environ\[)\s*\(?\s*[\"']([A-Z][A-Z0-9_]+)[\"']"
    )
    for p in REPO.rglob("*.py"):
        if any(seg in p.parts for seg in (".venv", "venv", "__pycache__", ".git")):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in pat.finditer(text):
            matches.add(m.group(1))
    if not matches:
        return "_(none detected)_"
    first_seen: dict[str, str] = {}
    pat2 = re.compile(
        r"os\.(?:getenv|environ\.get|environ\[)\s*\(?\s*[\"'](" + "|".join(re.escape(m) for m in matches) + r")[\"']"
    )
    for p in REPO.rglob("*.py"):
        if any(seg in p.parts for seg in (".venv", "venv", "__pycache__", ".git")):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in pat2.finditer(text):
            var = m.group(1)
            if var not in first_seen:
                first_seen[var] = str(p.relative_to(REPO))
    rows = ["| Variable | First location |", "|---|---|"]
    for var in sorted(matches):
        loc = first_seen.get(var, "?")
        rows.append(f"| `{var}` | `{loc}` |")
    return "\n".join(rows)


def gen_tests() -> str:
    tests_dir = REPO / "tests"
    if not tests_dir.exists():
        return "_(no tests/ directory)_"
    rows = ["| File | Test count | Tests |", "|---|---|---|"]
    func_pat = re.compile(r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)
    total = 0
    for p in sorted(tests_dir.glob("test_*.py")):
        text = p.read_text(encoding="utf-8")
        funcs = func_pat.findall(text)
        total += len(funcs)
        sample = ", ".join(f"`{f}`" for f in funcs[:3])
        if len(funcs) > 3:
            sample += f", … (+{len(funcs)-3} more)"
        rows.append(f"| [`tests/{p.name}`](./tests/{p.name}) | {len(funcs)} | {sample} |")
    rows.append(f"| **Total** | **{total}** | |")
    return "\n".join(rows)


def gen_public_api() -> str:
    init = REPO / "m3xa_core" / "__init__.py"
    if not init.exists():
        return "_(no m3xa_core/__init__.py)_"
    text = init.read_text(encoding="utf-8")
    m = re.search(r"__all__\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return "_(no __all__ defined)_"
    names = re.findall(r"[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']", m.group(1))
    rows = ["| Symbol |", "|---|"]
    for n in names:
        rows.append(f"| `{n}` |")
    return "\n".join(rows)


def gen_tree() -> str:
    rows: list[str] = ["```"]
    top = sorted(
        p for p in REPO.iterdir()
        if not p.name.startswith(".")
        and p.name not in {"__pycache__", "node_modules", ".venv", "venv"}
    )
    for p in top:
        if p.is_dir():
            rows.append(f"{p.name}/")
            for child in sorted(p.iterdir())[:20]:
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                rows.append(f"  {child.name}{'/' if child.is_dir() else ''}")
        else:
            rows.append(p.name)
    rows.append("```")
    return "\n".join(rows)


def gen_meta() -> str:
    sha = "?"
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()[:10]
    except Exception:
        pass
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"- **Last regenerated:** {ts}\n"
        f"- **Commit:** `{sha}`\n"
        f"- **Generated by:** `tools/regenerate_body.py`"
    )


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------
def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("\"'")
    return fm


# ---------------------------------------------------------------------------
# Apply to BODY.md
# ---------------------------------------------------------------------------
SECTIONS = {
    "actors": gen_actors,
    "self_awareness": gen_self_awareness,
    "scrapers": gen_scrapers,
    "expertises": gen_expertises,
    "concepts": gen_concepts,
    "stack": gen_stack,
    "env_vars": gen_env_vars,
    "tests": gen_tests,
    "public_api": gen_public_api,
    "tree": gen_tree,
    "meta": gen_meta,
}


def _apply_section(text: str, name: str, content: str) -> str:
    start = f"<!-- AUTOGEN:start:{name} -->"
    end = f"<!-- AUTOGEN:end:{name} -->"
    if start not in text or end not in text:
        print(f"WARNING: no AUTOGEN markers for '{name}' in BODY.md — skipping", file=sys.stderr)
        return text
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    return pattern.sub(f"{start}\n{content}\n{end}", text, count=1)


def regenerate(body_text: str) -> str:
    intermediate = body_text
    for name, fn in SECTIONS.items():
        if name == "meta":
            continue
        intermediate = _apply_section(intermediate, name, fn())
    content_changed = _strip_meta(intermediate) != _strip_meta(body_text)
    if content_changed:
        return _apply_section(intermediate, "meta", SECTIONS["meta"]())
    return intermediate


def _strip_meta(text: str) -> str:
    pattern = re.compile(
        r"(<!-- AUTOGEN:start:meta -->).*?(<!-- AUTOGEN:end:meta -->)", re.DOTALL
    )
    return pattern.sub(r"\1<PLACEHOLDER>\2", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Exit 1 if BODY.md is out of sync")
    args = parser.parse_args()

    if not BODY.exists():
        print(f"ERROR: {BODY} not found", file=sys.stderr)
        return 2

    current = BODY.read_text(encoding="utf-8")
    new = regenerate(current)

    if args.check:
        if current != new:
            print("BODY.md is out of sync with the codebase.", file=sys.stderr)
            print("Run: python tools/regenerate_body.py", file=sys.stderr)
            return 1
        print("BODY.md is in sync.")
        return 0

    if current == new:
        print("BODY.md already up to date.")
        return 0

    BODY.write_text(new, encoding="utf-8")
    print(f"Regenerated BODY.md ({len(SECTIONS)} sections).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
