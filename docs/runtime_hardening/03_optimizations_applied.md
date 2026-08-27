# Optimizations applied

## 1. Unified runtime timing and fingerprints

Added `apps/api/app/observability/runtime_timing.py` and integrated it across task creation, runtime preparation/execution, result presentation, and completion. The trace is bounded (event and fingerprint caps), stores no raw prompt/answer, and is persisted inside the existing structured result so the existing task/result contract remains intact.

This turns the runtime into an inspectable causal graph: request setup and routing can be separated from planner/context work, model/RAG/tool work can be separated from post-processing and commits, and persisted SSE timing can be compared with server-side stage timing.

## 2. Bounded knowledge retrieval cache

Added a bounded, refresh-invalidated LRU-style cache in `apps/api/app/services/knowledge_base.py`. The key is the expanded query, selected course packs, and result limit; the cached value preserves retrieval ordering and evidence metadata while refreshing the observed latency. Cache size is controlled by the existing `context_cache_max_entries` setting and capped at 512 entries.

This is intentionally one behavior-preserving optimization. It targets repeated identical retrievals and does not change scoring, routing, provider selection, or answer generation.

## A/B evidence

Across the current repeated subset, the after-run RAG stage is P90/P95 87.00/182.00 ms in `local_mock` and 107.00/144.00 ms in `local_deterministic`. `STABILITY_GENERAL_001` RAG durations by repetition are `[43102.0, 0.0, 0.0]` and `[39635.0, 0.0, 0.0]`, respectively; the zero-duration repeats are cache-hit evidence. Because the two runs are separate local processes and background load is not fully controlled, these are directional runtime measurements rather than a production performance guarantee.
