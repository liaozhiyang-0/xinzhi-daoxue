# Plan 边界设计

## 1. 目标状态

本阶段不重写现有 Plan，而是定义唯一的未来边界：

```mermaid
flowchart LR
    I[User/API input] --> G[Goal]
    G --> CP[Canonical Plan Boundary]
    CP --> RA[Runtime Plan Adapter]
    RA --> EP[Execution Plan]
    EP --> K[Runtime Kernel]
    K --> B[Business Capability]
```

边界原则：

- `Goal` 描述要完成什么以及成功条件，不描述数据库状态；
- `Canonical Plan` 描述有序/可并行的能力节点和约束；
- `Runtime Plan` 是 Runtime Kernel 能恢复、检查点化和执行的不可变快照；
- `Execution Plan` 是当前业务 Agent 的检索、输入、预算和 Provider 执行策略；
- 运行开始后，Plan 通过 checkpoint 固定，resume 不重新理解用户目标。

## 2. 当前 Plan 来源

| 当前模块 | 当前职责 | Phase A 处理 | 未来职责 |
| --- | --- | --- | --- |
| `IntentPlanCompiler` | 从 `RouteDecision` 编译 `IntentExecutionPlan`，含 nodes、capabilities、tools、skills、success criteria | KEEP / canonical boundary candidate | 作为唯一 Goal→Canonical Plan 编译入口 |
| `AgentExecutionPlanner` | 根据 Registry、输入类型、RAG policy、预算和 availability 生成 `AgentExecutionPlan` | KEEP / execution policy | 作为 Canonical Plan→Execution Plan adapter 的一部分 |
| `RuntimeGoalPlanner` | 将显式 `RuntimeGoal.required_capabilities` 绑定到已注册 handler，生成 `AgentRunPlan` | KEEP / freeze | 只处理显式结构化 Goal，不承担业务路由 |
| `RuntimeBusinessRegistry.build_plan()` | 调用业务 Runtime 的 `build_plan()` 并绑定 route facts | KEEP / adapter | 逐步收敛为 Runtime Plan adapter，不复制目标理解 |
| `GenericGoalRuntimeService.build_plan()` | 对明确 opt-in 的 generic goal 做 capability plan | KEEP / opt-in | 继续保持显式 `runtime_goal_runtime.execute=true`，不成为默认 Planner |
| 各 Business Runtime `build_plan()` | 生成知识、研究、教学、学术求解的专用执行计划 | FREEZE interface | 逐步输出统一 Canonical Plan 或通过 adapter 兼容 |

## 3. 当前重复与风险

1. Task 创建阶段由 `IntentPlanCompiler` 生成计划；Runtime 准备阶段 route refinement 后可能重新编译。
2. `IntentExecutionPlan` 的节点目标与 `AgentExecutionPlan` 的执行策略分开存储，调用方容易把两者当成同一层。
3. `RuntimeGoalPlanner`、`GenericGoalRuntimeService` 和各业务 `build_plan()` 都能生成 `AgentRunPlan`，但输入契约不同。
4. `RuntimeBusinessRegistry` 还承担 route facts 绑定，容易变成隐式控制面。

Phase A 不删除这些实现，因为它们承担现有 Runtime resume、业务运行和 contract tests；只规定最终 owner，禁止新增第五套 Plan。

## 4. Canonical Plan Boundary 草案

```text
CanonicalGoal
  objective
  success_criteria
  constraints
  required_capabilities
  context_snapshot

CanonicalPlan
  plan_id / version
  goal
  ordered_or_parallel_nodes
  capability references
  budget / policy
  fallback policy
  success criteria

RuntimePlanAdapter
  CanonicalPlan -> AgentRunPlan
  bind registered handler_id
  preserve node identity/dependencies
  emit immutable runtime snapshot
```

当前阶段只允许通过既有字段表达上述概念，不新建数据库表，不改变 `AgentRunPlan`、`RuntimeGoal`、`RuntimeNode` 和 checkpoint payload。

## 5. 不变量

- plan node id 唯一，依赖只能指向同一 plan 的已知节点；
- Runtime 启动后不得用当前配置或新路由重写 checkpointed plan；
- Plan 编译不执行 Provider、RAG 或 Tool；
- 未注册的 capability/handler 必须 fail-closed；
- 业务结果提交仍由 Result Pipeline/Task Completion 负责，不由 Plan compiler 决定。

## 6. Planner 接入位置

后续 Planner 应位于 `Goal` 与 `Canonical Plan Boundary` 之间：

```text
API/Supervisor adapter
  -> Planner: understand goal + choose candidates
  -> TaskRouter: deterministic preflight
  -> Canonical Plan Compiler
  -> Runtime Plan Adapter
```

本 Phase A 不实现 Planner、不改变现有入口，只为未来把 `IntentPlanCompiler` 提升为 canonical boundary 保留兼容位置。
