# Phase B5：Planner Canary Takeover

## 当前 canary 范围

Canary 只允许在 `PLANNER_TAKEOVER_ENABLED=true` 且至少一个显式 allowlist 命中时
生效。当前验证范围为 provider-free 的 `GENERAL_QUESTION_V1` capability；未扩大到
Academic Solver、高风险科研能力或全量流量。默认配置仍为 OFF。

接管链路为：

```text
Request
  ↓
Supervisor API/legacy preparation
  ↓
TaskRouter deterministic preflight
  ↓
Planner takeover snapshot
  ↓
CanonicalPlan
  ↓
Runtime preparation adapter
  ↓
Runtime
```

Planner 接管后，Runtime preparation 会从已持久化的 canonical plan 生成
`AgentRunPlan`；`Runtime Kernel` 本身未修改。未命中 allowlist、Planner 失败或 canonical
plan 无法校验时，继续使用既有 Runtime/legacy compatibility path。

## Rollback

回滚只需关闭 `PLANNER_TAKEOVER_ENABLED`，或移除对应 Agent/scenario allowlist。旧的
`TaskRouter`、`OverallRoutingService` compatibility wrapper、Task/Runtime checkpoint
contract 均保留。resume 不重新 Planner，直接使用 checkpoint 中的 run plan；因此关闭
开关不会改变已经开始的 Run。

## 监控字段

任务输入、`plan.created` 和 debug trace 中保留 planner mode/status、route revision、
canonical plan identity、preflight/route parity、fallback reason、model calls、token、
cost、latency 与 terminal status。B5 验证未触发 Provider 调用。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov `
  apps/api/tests/test_planner_canary.py `
  apps/api/tests/test_planner_shadow_mode.py `
  apps/api/tests/test_runtime_request_preparation.py
```

验证结果只代表受控、离线的结构性 canary；不代表线上流量稳定性，也不自动扩大范围。
