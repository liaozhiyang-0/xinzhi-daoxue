# Phase B0：Planner 基线与兼容矩阵

状态：Phase B 实施基线，Planner takeover 默认关闭。

## 1. 当前入口基线

### `/tasks`

```text
POST /api/v1/tasks
  -> principal/scenario/document/session context
  -> TaskRouter.route(AgentRequest)
  -> TaskCreationService.create_queued(request, RouteDecision)
  -> IntentPlanCompiler.compile()
  -> Task.created / route.selected / intent.recognized / plan.created
  -> Task queued
  -> TaskExecutor.submit(task_id)
```

任务创建保持非阻塞；Provider、RAG、Tool 和 Runtime 执行发生在队列提交之后。

### `/chat`

```text
POST /api/v1/chat
  -> ScenarioCatalog / attachment normalization
  -> XZDSupervisor.prepare(AgentRequestV2)
  -> AgentRequest + RouteDecision + XZDGraphState
  -> TaskCreationService.create_queued()
  -> same Task/Runtime path as /tasks
```

Supervisor 当前仍执行兼容性的课程/意图识别和输入规范化；Phase B Planner 会在后续以旁路或受控 canary 接入，不改变旧协议。

## 2. Route/Plan/Context/Run identity

| 事实 | 当前字段/来源 | Phase B 要求 |
| --- | --- | --- |
| Task | `TaskModel.id` / `task_id` | 保持不变 |
| Request | `AgentRequest.task_id`、`options.request_id` | 保持不变 |
| Trace | `options.trace_id`、`TraceStore` | additive 记录 Planner lineage |
| Route | `RouteDecision.route_revision`、`route_trace`、`route_source` | Planner route 必须单独记录，不覆盖 baseline |
| Intent plan | `IntentExecutionPlan.plan_id/version`、`options._intent_plan` | 旧 payload 可读；Canonical adapter 增量挂载 |
| Execution plan | `AgentExecutionPlan`、`options._execution_plan` | 不改变默认执行路径 |
| Runtime plan | `AgentRunPlan.plan_id/version`、checkpoint | resume 使用 checkpointed snapshot |
| Context | SessionContext/ConversationContextBundle | 记录 bounded snapshot identity，不复制原始输入到 Planner trace |

## 3. Resume 基线

`TaskRuntimePreparationService` 和 `RuntimeRequestPreparationService` 在 resume 场景优先使用已保存的 request、execution plan、launch identity 和 checkpoint。resume 不应重新执行 Overall Router、Context rebuild 或任何未来 Planner 目标理解。

## 4. Compatibility matrix

| Contract | 当前使用位置 | 兼容策略 | 破坏性变更 |
| --- | --- | --- | --- |
| `AgentRequest` | Task/Chat/Runtime | additive internal options only | 禁止 |
| `RouteDecision` | TaskRouter/Supervisor/Runtime preparation | 保留旧字段，Planner route 作为 snapshot | 禁止 |
| `IntentExecutionPlan` | Task creation/Runtime preparation | 继续可序列化，Canonical adapter 读取 | 禁止 |
| `AgentExecutionPlan` | Runtime request preparation | 继续作为 execution policy | 禁止 |
| `AgentRunPlan` | Runtime Kernel/checkpoint | 作为 Runtime plan snapshot | 禁止 |
| `AgentResult` | Result Pipeline/API | 维持 output/evidence/status contract | 禁止 |
| Runtime checkpoint | AgentRun repositories | resume 只读 checkpointed plan/request | 禁止 |
| Event/SSE | Task events/stream | 只能追加可忽略 metadata | 禁止重排/改语义 |
| RAG/Tool/Provider | Business Runtime/handler registry | Planner 只能读取 descriptor/policy | 禁止 Planner 直接执行 |

## 5. Rollback baseline

Phase B feature flags 必须满足：

- `PLANNER_SHADOW_ENABLED=false` 时不执行 shadow；
- `PLANNER_TAKEOVER_ENABLED=false` 时真实 route/plan 仍由旧链路决定；
- Planner exception、invalid candidate、preflight rejection 都回到旧路径；
- resume 永远不因为当前 Planner 配置变化而改写已有 Run。

## 6. B0 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov apps/api/tests/test_planner_phase_b_baseline.py
```

这份基线不构成真实 Provider、生产流量或 canary 授权；后续 B4/B5 必须分别提供 parity 和 rollback 证据。
