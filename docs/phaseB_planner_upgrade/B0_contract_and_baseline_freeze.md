# Phase B0：Contract 与 Baseline 冻结

## 目标

在引入 Planner 前，冻结 Phase B 的兼容基线，确保后续任何变化都能与现状对比、回滚和审计。

本阶段允许少量测试、trace 和 contract 补充，但不实现 Planner。

## 必须完成

1. 建立 Phase B baseline：
   - `/tasks`
   - `/chat`
   - route
   - intent
   - plan
   - AgentRun
   - checkpoint
   - SSE
   - retry/resume/cancel
   - RAG/Tool/Provider gate
2. 明确并记录必须兼容的 contracts：
   - AgentRequest
   - RouteDecision
   - IntentExecutionPlan
   - AgentExecutionPlan
   - AgentRunPlan
   - AgentResult
   - Runtime checkpoint payload
   - Event protocol
3. 增加或补齐 lineage identity：
   - task_id
   - trace_id
   - route_revision
   - plan_id / plan_version（如现有字段不足，仅允许 additive）
   - context revision / snapshot identity
   - runtime run identity
4. 建立 Phase B baseline 文档：
   - 当前一次典型 `/chat` 调用的 route/plan/context 变化；
   - 当前一次典型 `/tasks` 调用；
   - 当前 resume 行为；
   - 当前 Overall Router 被触发与未触发的路径。
5. 建立回滚基准：
   - 明确 Planner feature flag 尚不存在或默认关闭；
   - 后续所有 Planner 能力必须可通过配置恢复旧路径。

## 禁止

- 不实现 PlannerService；
- 不改真实 routing 结果；
- 不删除 OverallRoutingService；
- 不改 Runtime Kernel；
- 不新增 public Agent；
- 不改数据库破坏性 schema。

## 允许 Codex 调整

可根据代码现状调整 baseline fixture、trace 字段位置、contract test 组织和 additive schema 字段。

## 交付物

至少包含：

- `docs/architecture/planner_phase_b_baseline.md`
- Phase B contract compatibility matrix
- 针对 route/plan/resume 的 baseline tests

## 结束条件

满足后立即停止：

- baseline 文档完成；
- 关键 contracts 被列出并有测试；
- route/plan/context identity 可追踪；
- 所有现有关键测试通过；
- 没有 Planner 真实代码路径投入执行。

最终回复：

```text
Phase B0 completed.
Baseline frozen.
Planner not implemented.
Stopped before B1.
```
