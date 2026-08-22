# Phase B3：Planner Shadow Mode

## 范围

Planner shadow mode 已接入两个非阻塞入口：`POST /api/v1/tasks` 与
`POST /api/v1/chat`。入口仍由现有 Supervisor、TaskRouter 和任务创建事务负责；
Planner 只读取已经完成的路由、会话上下文摘要和注册表事实，并写入可追踪的
`PlannerSnapshot`，不调用 Provider、RAG 或 Tool，也不改变任务路由、Task 状态或
Runtime 执行计划。

开关：

- `PLANNER_SHADOW_ENABLED=false`：默认关闭。
- `PLANNER_TAKEOVER_ENABLED=false`：独立于 shadow 的受控接管开关。
- `PLANNER_CANARY_AGENT_IDS` / `PLANNER_CANARY_SCENARIO_IDS`：接管时必须显式配置
  至少一个 allowlist；两个 allowlist 均为空时 fail-closed。

## 快照与可观测性

`PlannerSnapshot` 持久化在任务输入的 `_planner_snapshot`，并随 `plan.created` 事件
写入。debug execution API 只返回脱敏后的 Planner 快照。快照包含：

- 当前 route、Planner route、intent、capability、skills、tools；
- 当前 plan shape 与 canonical plan shape，以及 parity 布尔值；
- goal、候选能力、成功标准、约束、预算；
- `context_snapshot_id`、`registry_snapshot_id`、request/task/trace/plan identity；
- latency、model calls、token/cost/error/fallback 字段。

第一阶段实现是 provider-free deterministic adapter，`model_calls=0`、token/cost 为 0
是预期行为，不代表真实模型 Planner 性能。

## 失败安全与恢复

Planner 异常被转换为 `mode=failed`、`status=failed` 的快照，并标记
`planner_failure_legacy_path`；任务继续沿既有 route/plan 创建路径运行。Shadow 失败
不得使 Task 创建失败。

Runtime resume 使用 checkpoint 中保存的 request 与 execution plan，不重建会话上下文、
不重新路由、不重新运行 Planner。Planner takeover 运行路径还会跳过 Overall Router，
防止发生第二次智能路由。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov `
  apps/api/tests/test_planner_shadow_mode.py `
  apps/api/tests/test_runtime_request_preparation.py
```

上述测试覆盖两个入口、持久化/事件 lineage、Planner 失败回退和 takeover 对旧 Overall
Router 的隔离。
