"""claude_interaction_log — persistent session memory for coding-agent sessions.

When a coding agent (Claude Code, Cursor, etc.) talks to the running
system through a side channel (MCP tool, slash command), this component
persists the relevant context across sessions. The next agent that opens
the repo can pick up the previous agent's threads.

Storage: .m3xa/interaction_log/<session_id>.jsonl
"""
from __future__ import annotations


def record_event(*, session_id: str, role: str, content: str) -> None:
    """Append one event to the session log. Skeleton."""
    raise NotImplementedError


def session_context(session_id: str, *, last_n: int = 20) -> list[dict]:
    """Return the last N events for a session. Skeleton."""
    raise NotImplementedError
