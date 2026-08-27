# Final recommendations

## P0 — preserve the observability contract

Keep `runtime_timing.v1`, stage names, bounded fingerprints, and the sanitized benchmark artifacts as a regression gate. Any event or result-schema change should update the corresponding persistence and SSE tests together.

## P1 — remove avoidable cold retrieval

Confirm whether `rag_enabled=false` should bypass knowledge retrieval for `STABILITY_GENERAL_001`. If retrieval is required, profile and index the hot lexical path; if it is not required, short-circuit it. Keep the bounded cache for repeated requests and clear it whenever the knowledge index refreshes.

## P1 — isolate persistence from request execution

Reproduce the SQLite lock under controlled concurrency, then add a bounded retry/backoff or move concurrent production workloads to the supported server database. Do not hide lock failures behind a successful task status.

## P1 — establish a separately authorized provider baseline

Extend the isolated real-provider run beyond the current 48 CT solver cases only after explicit cost/rate approval. Keep one output per provider and compare stage latency, fallback rate, tool activation, and first-content-available latency; do not combine provider-backed numbers with the local mock/deterministic baseline.

## P1 — make streaming latency measurable

If token-level TTFT is a release requirement, add an explicit token-delta SSE contract and corresponding order/reconnect tests. Until then, retain the honest first-content-available label used by this evidence pack.

## Release gate suggestion

Require: no raw-content leakage; route/status stability ≥99% on the representative subset; zero unexpected persistence errors; no new P95 regression in the full catalog; and an explicit disposition for every top-20 slow case.
