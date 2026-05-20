"""Pytest mirror of the CI anonymization check."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_no_real_source_names_in_repo():
    """No forbidden source name leaks into the public repo.

    The hashed blocklist is at .anonymization-blocklist.sha256.
    The plaintext source is .anonymization-blocklist.txt (gitignored).
    """
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_anonymization.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        msg = (
            f"Anonymization check failed.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}\n"
            f"Fix: replace real source names with aliases from docs/source_naming.md."
        )
        raise AssertionError(msg)
