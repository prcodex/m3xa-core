---
name: feedcache_block_on_stale
description: Why the FeedCache blocks on stale reads (instead of stale-while-refresh) for human/bursty traffic
type: concept
applies_to: m3xa-core
status: stub
---

# FeedCache — block on stale

> The FeedCache stores the last-loaded subset of `unified_feed` in memory for fast retrieval. The original design was stale-while-refresh: serve stale data, kick off a background refresh. **It was wrong.** Human traffic is bursty — a user types five questions in 90 seconds. Three of them got yesterday's data because the refresh hadn't completed. The fix was block-on-stale: the first request that detects stale data blocks until the refresh completes, then everyone reads fresh.

Stub. Full essay covers:

- Stale-while-refresh vs block-on-stale — the trade-off
- Why "machine traffic" (cron-driven, paced) and "human traffic" (bursty) want different cache behavior
- The implementation in `m3xa_core/backends/feed_cache.py`
- How to detect "stale" cheaply (the `last_ingest_at` timestamp on `unified_feed`)
- Lock contention: only one refresh runs at a time; concurrent stale-detectors block on the same future
