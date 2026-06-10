"""health_caveats_writer — temporary "the X scraper is degraded" warnings injected into RAG.

Writes short markdown caveats with a 6-hour TTL. The retriever reads
active caveats and prepends them to the synthesizer context. Why 6 hours:
long enough that the agent stays honest about the gap; short enough that
yesterday's broken scraper doesn't poison today's response.

Storage: .m3xa/health/caveats/<id>.md with frontmatter
{created_at, expires_at, topic, severity}.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

CAVEAT_ROOT = Path.home() / ".m3xa" / "health" / "caveats"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def _parse_fm(text: str) -> tuple[dict, str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def write_caveat(
    *,
    topic: str,
    message: str,
    ttl_hours: int = 6,
    severity: str = "warn",
    root: Path | None = None,
) -> str:
    """Create a new caveat. Returns the file path.

    `severity` is informational — the retriever may decide to prepend
    `error`-level caveats more visibly than `info`.
    """
    out_dir = root or CAVEAT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=timezone.utc)
    expires = now + timedelta(hours=ttl_hours)
    cid = uuid.uuid4().hex[:8]
    path = out_dir / f"{cid}.md"
    path.write_text(
        f"""---
caveat_id: {cid}
created_at: {now.isoformat()}
expires_at: {expires.isoformat()}
topic: {topic}
severity: {severity}
---

{message.strip()}
""",
        encoding="utf-8",
    )
    return str(path)


def active_caveats(*, topic: str | None = None, root: Path | None = None) -> list[str]:
    """Return non-expired caveat bodies, optionally filtered by topic.

    Expired files are deleted on read — caveats are bounded by design.
    """
    src = root or CAVEAT_ROOT
    if not src.exists():
        return []
    now = datetime.now(tz=timezone.utc)
    bodies: list[str] = []
    for path in sorted(src.glob("*.md")):
        try:
            fm, body = _parse_fm(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        expires = fm.get("expires_at")
        if expires:
            try:
                if datetime.fromisoformat(expires) < now:
                    path.unlink(missing_ok=True)
                    continue
            except ValueError:
                pass
        if topic and fm.get("topic", "").lower() != topic.lower():
            continue
        bodies.append(body.strip())
    return bodies
