"""claude_interaction_log — persistent session memory for coding-agent sessions.

When a coding agent (Claude Code, Cursor, etc.) talks to the running
system through a side channel (MCP tool, slash command), this component
persists the relevant context across sessions. The next agent that opens
the repo can pick up the previous agent's threads.

Storage: .m3xa/interaction_log/<session_id>.jsonl
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_ROOT = Path.home() / ".m3xa" / "interaction_log"


def _session_path(session_id: str, root: Path | None = None) -> Path:
    src = root or LOG_ROOT
    src.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "default"
    return src / f"{safe}.jsonl"


def record_event(
    *,
    session_id: str,
    role: str,
    content: str,
    root: Path | None = None,
) -> None:
    """Append one event to the session log.

    `role` is free-form (user / assistant / tool / system) so different
    agents can use their native vocabulary. `content` is truncated at
    16k chars — longer payloads belong somewhere else.
    """
    path = _session_path(session_id, root)
    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "role": role,
        "content": content[:16_000],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def session_context(
    session_id: str,
    *,
    last_n: int = 20,
    root: Path | None = None,
) -> list[dict]:
    """Return the last N events for a session.

    Reads the JSONL once; if the file is huge, only the tail is parsed.
    """
    path = _session_path(session_id, root)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-last_n:]
    out: list[dict] = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
