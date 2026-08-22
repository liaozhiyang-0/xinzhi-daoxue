# Phase B2：Canonical Plan 与 Runtime Adapter

## 1. 唯一语义边界

```text
PlannerSnapshot
  -> CanonicalGoal + CanonicalPlan
  -> CanonicalPlanAdapter
  -> AgentRunPlan / Runtime Kernel
```

层级不能混用：

- `CanonicalGoal`：目标、课程/意图、约束和成功条件；
- `CanonicalPlan`：能力节点、依赖、可选性、选择结果和预算；
- `AgentExecutionPlan`：RAG、输入模式、Provider timeout、retrieval policy 等执行策略；
- `AgentRunPlan`：Runtime 可 checkpoint、恢复和调度的不可变计划。

## 2. Adapter matrix

| 旧 contract | adapter | 结果 |
| --- | --- | --- |
| `IntentExecutionPlan` | `CanonicalPlanAdapter.from_intent_plan()` | 读取已有 route/plan，形成 CanonicalGoal/Plan |
| `CanonicalPlan` | `to_intent_plan()` | 保持 Task/legacy payload 可读 |
| `CanonicalPlan` | `to_runtime_plan()` | 生成现有 `AgentRunPlan`/`RuntimeNode` |
| `AgentRunPlan` | `from_agent_run_plan()` | 将已 checkpoint/运行计划映射回 canonical 视图 |
| `RuntimeGoal` | `from_runtime_goal()` | 将显式 generic goal 映射为 canonical 目标 |
| `AgentExecutionPlan` | `execution_policy()` | 明确它是 execution policy，不复制为 Goal |

## 3. 不变量

1. Adapter 是纯转换，不调用 Provider、RAG、Tool 或数据库。
2. Node id、依赖关系和 success criteria 不能在转换中静默丢失。
3. `AgentRunPlan` 启动后仍由 Runtime checkpoint 作为事实源。
4. 旧 `IntentExecutionPlan`、`AgentExecutionPlan` 和 `AgentRunPlan` 类不删除。
5. 不新增数据库列，不改 Task/Run/SSE contract。

## 4. 当前接入策略

当前 Planner snapshot 由 `IntentPlanCompiler` 的 deterministic output 适配而来；默认 route/plan 不被替换。`TaskCreationService` 在 shadow 或 takeover flag 开启时记录 snapshot；Runtime preparation 在 takeover snapshot 已确认时跳过第二次 Overall Router refinement，避免两个智能 owner 并存。

## 5. Resume

resume 路径继续从 checkpointed request/plan 恢复，不能重新调用 `PlannerService`。Canonical plan 只作为现有 plan 的可序列化边界和 debug/evaluation 视图。
