# Runtime baseline

本目录的基线是现有 Runtime 链路上的本地可重复基准，不代表生产准确率，也不把 mock/deterministic 结果冒充真实模型结果。案例目录为 `150` 个，原始问答未写入报告：`raw_prompts_stored=False`、`raw_answers_stored=False`。

运行命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_runtime_stability.py --mode both --limit 150 --repeat 1 --output docs\runtime_hardening\runtime_baseline.json
```

| 模式 | 案例运行数 | 通过率 | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|
| `local_mock` | 150 | 79.33% | 1504.00 | 3355.00 | 28810.00 |
| `local_deterministic` | 150 | 79.33% | 1429.00 | 2518.00 | 34211.00 |

该基线只用于和 `runtime_after.json` 做同口径比较。真实 Provider、浏览器和工作区六案例矩阵均单独列出，不混入本地延迟数字。
