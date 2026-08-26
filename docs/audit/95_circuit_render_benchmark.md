# 95 电路绘图基准报告

日期：2026-08-26

命令：

```powershell
.venv\Scripts\python.exe scripts/benchmark_circuit_rendering_v2.py --iterations 200
```

本次运行覆盖 CT、AE、DE 各 1 个代表性案例，每案例执行 200 次，连续完成 600 次 professional SVG 渲染，失败数为 0。

| 阶段 | CT p50/p95/p99 ms | AE p50/p95/p99 ms | DE p50/p95/p99 ms |
| --- | ---: | ---: | ---: |
| validation | 0.038 / 0.056 / 0.080 | 0.056 / 0.092 / 0.135 | 0.033 / 0.043 / 0.054 |
| layout | 0.315 / 0.619 / 1.114 | 0.288 / 0.401 / 0.710 | 0.220 / 0.249 / 0.287 |
| render + project | 0.454 / 0.671 / 1.251 | 0.473 / 0.999 / 1.319 | 0.345 / 0.497 / 0.801 |

这是 Windows 本地单次基准，不代表生产容量或跨机器性能承诺。
