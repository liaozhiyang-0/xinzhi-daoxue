# 本地自动调度延迟报告

环境：Windows 11、项目 `.venv`、2026-07-20。命令：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_auto_routing.py
```

脚本对 70 条 fixture 重复 20 次，共 1,400 次，使用 `perf_counter` 单独测量材料提取和路由；不含数据库、RAG、网络或云端时间。

| 阶段 | p50 | p95 | 目标 | 结论 |
|---|---:|---:|---:|---|
| 材料提取 | 0.434 ms | 0.879 ms | < 50 ms | 达标 |
| 本地路由 | 0.572 ms | 1.250 ms | < 50 ms | 达标 |

1,400 次中 1,300 次 selected、100 次 unresolved，对应每轮 65/5。明确请求无需云端 Router 的比例为 92.86%；Router 因 Flow 未配置实际调用比例为 0%，可配置时预计候选比例为 7.14%。

本轮没有保存修改前同口径的延迟样本，因此不报告虚构的前后差值。ExecutionPlan、Validator、RAG、本地总前处理和自动重路由端到端分位数尚未由本脚本覆盖；真实最小云端检查的单次耗时为 9.1–44.5 秒，不能当成本地延迟分位数。后续应在持久化 Trace 指标上补同机 p50/p95，并分别统计 RAG 与非 RAG。
