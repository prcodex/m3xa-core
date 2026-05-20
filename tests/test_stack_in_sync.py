"""Pytest mirror of the CI stack-in-sync check."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_stack_docs_in_sync_with_pyproject():
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_stack_in_sync.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        msg = (
            f"Stack docs out of sync with pyproject.toml.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}\n"
            f"Fix: see docs/stack/README.md."
        )
        raise AssertionError(msg)
