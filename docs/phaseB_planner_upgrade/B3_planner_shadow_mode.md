# Phase B3：Planner Shadow Mode 接入

## 目标

让 Planner 在真实任务旁路运行，只生成决策和计划，不改变实际 route、plan 或 Runtime 行为。

```text
User Request
   ├─> Current Route/Plan ─> Real Execution
   |
   └─> Planner Shadow ─> PlannerSnapshot ─> Trace Only
```

## 必须完成

1. `/chat` 与 `/tasks` 均可选择性触发 Planner Shadow。
2. Planner Shadow 使用与真实请求一致的 normalized request、routing context snapshot、registry snapshot、session continuity summary。
3. Planner 输出只写 trace / debug/audit / evaluation record。
4. Planner 不能修改 RouteDecision、Task.agent_id、Runtime plan，也不能触发 Provider/Tool/RAG 执行。
5. 增加 Planner latency/token/cost/exception 可观测性。
6. Planner failure 不得导致真实任务失败。
7. Shadow 必须有单独 feature flag。
8. resume 默认不重新运行 shadow planner，除非明确做审计 replay。

## 对比记录

至少记录：

```text
current_route
planner_route
current_intent
planner_intent
current_capability
planner_capability
current_tools
planner_tools
current_skills
planner_skills
current_plan_shape
planner_plan_shape
route_match
plan_match
planner_confidence
planner_reason_codes
```

## 禁止

- Planner 不得改变真实执行；
- 不关闭 Overall Router；
- 不做 canary；
- 不做 automatic promotion；
- 不让 Planner 生成未注册 Agent/Skill/Tool ID。

## 交付物

- shadow integration
- trace schema
- shadow feature flag
- shadow tests
- debug/evaluation visibility

## 结束条件

- `/chat` 与 `/tasks` 都能旁路生成 PlannerSnapshot；
- Planner failure 不影响真实任务；
- route/plan diff 可查询；
- 测试通过；
- production behavior 与 B2 前一致。

最终回复：

```text
Phase B3 completed.
Planner shadow mode active behind flag.
No production takeover.
Stopped before B4.
```
