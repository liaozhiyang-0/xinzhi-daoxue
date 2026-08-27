# Latency breakdown

The runtime trace is `runtime_timing.v1`. It records the causal chain `request_preparation → routing → planner → context_build → runtime_execute → {rag_query_rewrite/rag_retrieval/rag_rerank/rag_evidence_build/model_call_N/tool/circuit_render} → reflection → quality_gate → presentation → session_commit → result_commit`, plus persisted SSE timing and the first-content-available event. Fingerprints link prepared input, plan, context, RAG query, evidence IDs, quality-gate input, and presentation without retaining raw content.

## `local_mock` full catalog

- `full 150-case run`：150 次运行、150 个案例，通过率 78.00%；P50 2035.00 ms, P90 4481.00 ms, P95 6662.00 ms, max 30169.00 ms, mean 2514.93 ms；passed=117, failed=33。
SSE first-event latency: P50 35.87 ms, P90 48.28 ms, P95 55.80 ms, max 82.76 ms, mean 35.33 ms. First-content-available latency: P50 1693.63 ms, P90 2597.43 ms, P95 3139.31 ms, max 30029.11 ms, mean 1965.73 ms; the current transport has no token-delta stream, so this is not token-level TTFT.

| 阶段 | P50 ms | P95 ms | 最大 ms | 样本数 |
|---|---:|---:|---:|---:|
| `circuit_render` | 0.03 | 0.05 | 0.28 | 148 |
| `context_build` | 52.80 | 109.47 | 159.87 | 148 |
| `math_postprocess` | 1.46 | 7.99 | 9.76 | 148 |
| `model` | 0.00 | 0.00 | 0.00 | 148 |
| `planner` | 2.33 | 3.61 | 4.57 | 148 |
| `presentation` | 0.64 | 1.43 | 1.81 | 148 |
| `quality_gate` | 42.60 | 84.64 | 146.00 | 148 |
| `rag` | 0.00 | 210.00 | 29182.00 | 148 |
| `rag_query_rewrite` | 0.06 | 0.13 | 0.19 | 106 |
| `rag_retrieval` | 179.34 | 398.62 | 29183.01 | 106 |
| `reflection` | 0.28 | 0.54 | 0.79 | 148 |
| `request_preparation` | 51.83 | 84.44 | 241.15 | 148 |
| `result_commit` | 197.20 | 314.62 | 3314.63 | 148 |
| `result_validation` | 42.21 | 84.27 | 145.34 | 148 |
| `routing` | 91.98 | 178.15 | 225.24 | 148 |
| `runtime_execute` | 856.31 | 1745.64 | 29533.78 | 148 |
| `session_commit` | 58.02 | 120.28 | 151.12 | 148 |
| `task_commit` | 264.59 | 438.95 | 3425.62 | 148 |
| `tool` | 350.08 | 552.03 | 598.07 | 51 |
| `tool_execution` | 350.08 | 552.03 | 598.07 | 51 |

## `local_mock` representative repeat by round

| 重复轮次 | 案例数 | RAG P50 ms | RAG P95 ms | RAG 最大 ms | 总耗时 P50 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 48 | 0.00 | 377.00 | 43102.00 | 1780 |
| 2 | 48 | 0.00 | 0.00 | 0.00 | 1323 |
| 3 | 48 | 0.00 | 0.00 | 0.00 | 1309 |

## `local_deterministic` full catalog

- `full 150-case run`：150 次运行、150 个案例，通过率 78.67%；P50 1437.00 ms, P90 2309.00 ms, P95 2684.00 ms, max 40511.00 ms, mean 1861.05 ms；passed=118, failed=32。
SSE first-event latency: P50 18.17 ms, P90 21.39 ms, P95 23.21 ms, max 35.62 ms, mean 18.72 ms. First-content-available latency: P50 1174.95 ms, P90 1559.53 ms, P95 1659.22 ms, max 40214.20 ms, mean 1540.17 ms; the current transport has no token-delta stream, so this is not token-level TTFT.

| 阶段 | P50 ms | P95 ms | 最大 ms | 样本数 |
|---|---:|---:|---:|---:|
| `circuit_render` | 0.01 | 0.01 | 0.14 | 148 |
| `context_build` | 27.50 | 75.08 | 89.97 | 148 |
| `math_postprocess` | 0.74 | 13.71 | 24.85 | 148 |
| `model` | 0.00 | 0.00 | 0.00 | 148 |
| `planner` | 1.24 | 1.79 | 2.34 | 148 |
| `presentation` | 0.51 | 1.12 | 2.79 | 148 |
| `quality_gate` | 27.25 | 81.12 | 105.41 | 148 |
| `rag` | 0.00 | 219.00 | 39151.00 | 148 |
| `rag_query_rewrite` | 0.04 | 0.07 | 0.19 | 107 |
| `rag_retrieval` | 153.13 | 279.31 | 39151.52 | 107 |
| `reflection` | 0.13 | 0.20 | 1.31 | 148 |
| `request_preparation` | 25.56 | 49.02 | 94.41 | 148 |
| `result_commit` | 158.76 | 244.80 | 533.08 | 148 |
| `result_validation` | 26.65 | 80.91 | 105.18 | 148 |
| `routing` | 56.32 | 109.46 | 143.85 | 148 |
| `runtime_execute` | 616.85 | 1120.63 | 39577.38 | 148 |
| `session_commit` | 43.24 | 87.80 | 929.45 | 148 |
| `task_commit` | 203.99 | 317.87 | 1133.26 | 148 |
| `tool` | 241.77 | 341.35 | 394.02 | 52 |
| `tool_execution` | 241.77 | 341.35 | 394.02 | 52 |

## `local_deterministic` representative repeat by round

| 重复轮次 | 案例数 | RAG P50 ms | RAG P95 ms | RAG 最大 ms | 总耗时 P50 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 48 | 0.00 | 297.00 | 39635.00 | 1324 |
| 2 | 48 | 0.00 | 0.00 | 0.00 | 1290 |
| 3 | 48 | 0.00 | 0.00 | 0.00 | 1265 |

## Slowest full-run cases

The detailed sanitized list is in `top_slow_cases.json`. The current dominant outlier is case `STABILITY_GENERAL_001` reached 40511 ms total, with `runtime_execute` taking 39577.38 ms; it occurs in the local benchmark's knowledge/context path and is not a remote provider latency measurement.
