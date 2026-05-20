"""Pytest mirror of the CI body-in-sync check.

Catches BODY.md staleness during local development, before the developer
even commits. Same logic as .github/workflows/body_in_sync.yml.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_body_md_in_sync_with_code():
    """If BODY.md's AUTOGEN sections are stale, fail.

    Fix locally: `python tools/regenerate_body.py`
    """
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "regenerate_body.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        msg = (
            f"BODY.md is out of sync with the codebase.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}\n"
            f"Fix: python tools/regenerate_body.py"
        )
        raise AssertionError(msg)
