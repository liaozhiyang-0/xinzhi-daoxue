# Phase B2：Canonical Plan 与 Runtime Adapter

## 目标

建立唯一的未来 Plan 语义边界，消除继续新增计划方言的风险。

```text
Planner Goal
   ↓
Canonical Plan
   ↓
Runtime Plan Adapter
   ↓
AgentRunPlan / Runtime Kernel
```

## 非协商原则

1. Canonical Plan 描述“要执行哪些能力节点以及成功条件”。
2. Runtime Plan 描述“Runtime 如何持久化、恢复和执行节点”。
3. Execution Policy 描述“RAG、Provider、输入模式、预算等具体执行策略”。
4. 三者不能再次混为一层。
5. Runtime 启动后 plan snapshot 不可被当前配置静默重写。
6. Resume 不重新调用 Planner。

## 必须完成

1. 定义 CanonicalGoal / CanonicalPlan contract 或等价结构。
2. 为现有 IntentExecutionPlan、AgentExecutionPlan、AgentRunPlan、RuntimeGoal 建立兼容 adapter。
3. 明确唯一 Plan owner。
4. Planner 产出的 plan 能转换为现有 Runtime 可执行结构。
5. 旧计划仍然可以转换到 canonical boundary 或继续通过 legacy adapter 执行。
6. 建立 plan version / plan identity / source lineage。
7. plan compiler 不得调用 Provider/RAG/Tool。

## 重点审查

必须确认各 Business Runtime 的 `build_plan()`：哪些是领域约束、哪些是重复目标理解、哪些未来应变成 adapter。本阶段禁止大规模删除。

## 禁止

- 不替换真实执行路径；
- 不删除旧 plan 类；
- 不重写 Runtime Controller；
- 不修改 checkpoint 语义；
- 不进入 Skill Framework。

## 交付物

- canonical plan contracts
- adapters
- plan compatibility tests
- `docs/architecture/canonical_plan_phase_b.md`

## 结束条件

- PlannerSnapshot → CanonicalPlan → AgentRunPlan 可以在测试中闭环；
- 旧 plan payload 仍兼容；
- checkpoint resume 测试通过；
- 真实 routing/execution 仍未由 Planner 接管。

最终回复：

```text
Phase B2 completed.
Canonical Plan boundary established.
Runtime compatibility preserved.
Stopped before B3.
```
