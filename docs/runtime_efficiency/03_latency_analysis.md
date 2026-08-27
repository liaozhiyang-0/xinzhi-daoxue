# Latency analysis

以下阶段数据来自最新 `runtime_after.json` 的本地报告。P50/P95 是 case-run 统计；真实 Provider 延迟另见 `05_ab_results.md`。

## `local_mock`

总耗时 P50/P95/最大：2035.00/6662.00/30169.00 ms。

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

## `local_deterministic`

总耗时 P50/P95/最大：1437.00/2684.00/40511.00 ms。

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

## Top slow cases

详单见 `top_slow_cases.json`；slow case 按总耗时排序并保留阶段、计数、fallback 与终态原因，不保留原始问答。

来源：`runtime_after.json full 150-case records`。
