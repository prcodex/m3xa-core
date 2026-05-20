# PyArrow

**Package:** `pyarrow`  •  **Version pin:** `>=15.0.0`  •  **Role:** Arrow / Parquet runtime backing LanceDB

## What it does

Apache Arrow's Python bindings. We don't call it directly — it's the columnar engine LanceDB sits on. Pinned explicitly because LanceDB's wheel constraints are looser than what we've actually tested against, and a too-old PyArrow surfaces as `ImportError: cannot import name ...` from inside LanceDB.

## Where it's used in m3xa-core

Transitively, via `lancedb`. No direct imports in the repo.

## Why we picked it

Not a choice — LanceDB requires it. We pin the lower bound to avoid the diagnostic-unfriendly version-mismatch failures.

## Alternatives considered

None applicable — this is a transitive runtime, not a swappable component.

## How to swap it out

Don't. If you swap LanceDB for a different vector DB (see `lancedb.md`), this dependency leaves with it.

## Links

- Homepage: <https://arrow.apache.org/docs/python/>
- GitHub: <https://github.com/apache/arrow>
- Last verified: 2026-05-19
