# 99 电路绘图 v2 稳定基线

日期：2026-08-26

## 稳定边界

- 冻结 `SOLVER_CT v1.0` 不直接修改。
- 默认 professional SVG；无可信 CircuitIR 不推断拓扑。
- invalid/uncertain IR 对 Solver 非致命，失败状态和复核边界可见。
- CT/AE/DE 各 50 个合成基准案例，另有 600 次连续渲染基准。
- 浏览器卡片隔离展示，支持安全清理、缩放和 light/dark token。

## 发布前命令

```powershell
scripts\check.ps1
Push-Location apps/web; npm run typecheck; npm run build; Pop-Location
.venv\Scripts\python.exe scripts\benchmark_circuit_rendering_v2.py --iterations 200
```

本次最终检查结果为 `2024 passed, 15 skipped, 14 warnings`；前端 typecheck/build 和 600 次绘图基准也已通过。不得把 Mock 或短 soak 结果描述为真实 Provider/生产性能。
