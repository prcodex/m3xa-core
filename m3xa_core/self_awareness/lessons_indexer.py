"""lessons_indexer — LESSONS.md -> tagged JSON for runtime retrieval.

Parses LESSONS.md, tags each lesson by the domain(s) it applies to, and
writes a JSON index at .m3xa/lessons_index.json. The synthesizer can
pull a relevant lesson into context when the query touches a known
failure mode.

Format expectation: each lesson is an H2 (`## Lesson title`) followed by
prose. The first paragraph after the heading is the lesson body. Optional
inline tags `[tag:rates, tag:central_bank]` after the heading drive the
domain index.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LESSONS_FILE = Path(__file__).resolve().parent.parent.parent / "LESSONS.md"
INDEX_FILE = Path.home() / ".m3xa" / "lessons_index.json"

H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TAG = re.compile(r"\[tag:([a-z0-9_,\s]+)\]", re.IGNORECASE)


def _parse(text: str) -> list[dict]:
    """Split LESSONS.md into a list of lesson dicts."""
    lessons: list[dict] = []
    headings = list(H2.finditer(text))
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()

        tag_matches = TAG.findall(body)
        tags: list[str] = []
        for raw in tag_matches:
            tags.extend(t.strip().lower() for t in raw.split(","))

        # First paragraph is the summary
        first_para = body.split("\n\n", 1)[0]
        summary = re.sub(TAG, "", first_para).strip()

        lessons.append(
            {
                "title": title,
                "tags": sorted(set(tags)),
                "summary": summary[:400],
                "body": body,
            }
        )
    return lessons


def rebuild_index(*, lessons_path: Path | None = None, index_path: Path | None = None) -> int:
    """Re-parse LESSONS.md and rewrite the index. Returns lesson count."""
    src = lessons_path or LESSONS_FILE
    dst = index_path or INDEX_FILE
    if not src.exists():
        return 0
    lessons = _parse(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(lessons, indent=2), encoding="utf-8")
    return len(lessons)


def lessons_for_topic(topic: str, *, index_path: Path | None = None) -> list[dict]:
    """Return lessons whose tag set intersects `topic`.

    Case-insensitive tag match. If the topic isn't a tag, falls back to
    substring search over the lesson summary.
    """
    dst = index_path or INDEX_FILE
    if not dst.exists():
        return []
    lessons = json.loads(dst.read_text(encoding="utf-8"))
    topic_l = topic.lower()
    hits = [l for l in lessons if topic_l in l.get("tags", [])]
    if hits:
        return hits
    return [l for l in lessons if topic_l in l.get("summary", "").lower()][:5]
