# A/B results

A=基线，B=加入现有 RAG 有界缓存与本轮诊断补齐后的运行结果。两者均为本地 mock/deterministic 口径；不把本地耗时外推为生产性能。

| 模式 | 指标 | A 基线 | B 最新 | 变化 |
|---|---|---:|---:|---:|
| `local_mock` | P50 ms | 1504.00 | 2035.00 | +35.31% |
| `local_mock` | P95 ms | 3355.00 | 6662.00 | +98.57% |
| `local_mock` | 最大 ms | 28810.00 | 30169.00 | +4.72% |
| `local_mock` | 平均 ms | 1843.39 | 2514.93 | +36.43% |
| `local_mock` | fallback 次数/率 | 55 / 36.67% | 55 / 36.67% | +0.00% |
| `local_deterministic` | P50 ms | 1429.00 | 1437.00 | +0.56% |
| `local_deterministic` | P95 ms | 2518.00 | 2684.00 | +6.59% |
| `local_deterministic` | 最大 ms | 34211.00 | 40511.00 | +18.42% |
| `local_deterministic` | 平均 ms | 1705.73 | 1861.05 | +9.11% |
| `local_deterministic` | fallback 次数/率 | 55 / 36.67% | 55 / 36.67% | +0.00% |

解释：P50 改善不能掩盖 P95 或最大值回归；长尾主要看 `rag_retrieval`、`runtime_execute`、`result_commit/task_commit` 和未配置模型导致的降级路径。fallback 率必须与失败分类一起解读，不把预期的 provider-unavailable 降级写成成功模型调用。

## Real Provider evidence

受控真实报告：provider=dashscope，48 个 case-run，状态={'passed': 48}，模型调用 46 次。模型耗时 P50/P95=5914.00/10632.00 ms；总 case 耗时 P50/P95=7673.00/28968.00 ms。该报告是单独的 CT 求解切片，不是六课程生产基线。

## Browser evidence

`/workspace` 浏览器会话 1 个、4 轮；首轮完成 11233 ms；console errors=0；终态检查={'input_reenabled': True, 'stop_disabled': True, 'execution_status_completed': True}。
