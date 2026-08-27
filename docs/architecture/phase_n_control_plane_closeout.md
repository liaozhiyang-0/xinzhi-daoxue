# Phase N v2：Planner-Driven Control Plane 收口

> 收口日期：2026-08-23
> 分支：`refactor/platform-modernization`

## 1. 收口结论

Phase N v2 将新任务的生产控制权收敛到：

```text
Unified Ingress
  → GoalContract
  → deterministic preflight
  → PlannerService
  → CapabilityBindingRegistry + SkillRegistry/SkillPolicy
  → CanonicalPlan
  → RuntimeTaskEngine / PlanExecutor
  → verification / governance / human review
  → result commit / SSE / Student HTML
```

`/api/v1/chat` 和 `/api/v1/tasks` 共享 `UnifiedRequestPreparationService`。`TaskRouter` 保留为 deterministic preflight 和旧请求兼容映射；它不再是 active 生产计划 owner。Planner 生成并持久化 `CanonicalPlan`，Runtime 只执行已验证的计划，不重新理解用户目标。

## 2. 控制权矩阵

| 组件 | 当前 active 职责 | 处理 |
| --- | --- | --- |
| Unified ingress | 归一化 Goal、模态、附件和约束 | KEEP |
| GoalContract | 统一目标合同，不包含最终 Agent route | KEEP |
| TaskRouter | deterministic preflight、可用性和粗粒度 hint | FREEZE / COMPATIBILITY |
| Supervisor | `/chat` 历史适配包装 | MERGE into unified ingress boundary |
| PlannerService | 唯一 active 计划 owner | KEEP |
| CapabilityBindingRegistry | capability → reviewed handler binding | KEEP |
| SkillRegistry / Retriever / Policy | 技能检索、资格和证据约束 | KEEP |
| OverallRoutingService | active 不注入；shadow compatibility only | FREEZE / REMOVE after importer-zero audit |
| FallbackRoutingService | active 不注入；shadow compatibility only | MERGE into Planner fallback policy in later cleanup |
| IntentPlanCompiler | canonical/old contract adapter | FREEZE / REMOVE from default production owner |
| RuntimeBusinessRegistry | capability-bound business adapter compatibility boundary | KEEP temporarily; migrate handlers incrementally |
| RuntimeTaskEngine / PlanExecutor | durable execution、checkpoint、resume、control | KEEP |
| `legacy-runtime:*` | active 缺少计划时 fail closed；旧 checkpoint reader compatibility | FREEZE / REMOVE after persisted-reader audit |
| scenario_catalog | UI metadata、goal hint、证据和展示约束 | KEEP as metadata only |
| TaskPresentation / ResultPresentation | capability/presentation profile driven output | KEEP |

## 3. 已淘汰的生产权力

- `/chat` 与 `/tasks` 的独立目标理解已合并为统一 GoalContract 入口。
- active Runtime preparation 不调用 Overall Router，不做二次 route rewrite。
- CanonicalPlan 创建后不允许 route mutation；route revision 进入 Planner lineage。
- active 任务没有有效 CanonicalPlan 时失败关闭，不自动生成 `legacy-runtime:*` 计划。
- 六案例不再要求固定 Agent 专属前端页面；展示层按 capability、section type 和 presentation profile 渲染。
- `general_answer`、`learning.path_plan`、`knowledge.govern` 的兼容别名按声明 intent 显式归一化，避免普通问答误显示为治理或学习路径。

## 4. 必须保留的兼容面

以下接口和语义不得在后续 Phase P 破坏：

- Task API 的非阻塞 `202` 创建语义；
- `AgentRequest`、`AgentResult`、Runtime Plan/Run 和 checkpoint snapshot；
- RAG retrieval/context/citation contract；
- ToolRegistry、RuntimeHandlerRegistry 和 timeout/approval/side-effect metadata；
- Task event sequence、SSE reconnect、terminal state；
- `waiting_review` / `waiting_user`、pause/resume/approve/input；
- AC-01 图片材料导入与不确定性披露；
- Legacy 三栏工作台、统一 Markdown/KaTeX 和数学回归夹具；
- `ACADEMIC_PROBLEM_SOLVER` 的 CT CoursePack 与确定性校验能力。

## 5. 阶段验证

### Controlled six-case gate

```text
valid: true
case_count: 6
invalid_capabilities: 0
unregistered_skills: 0
route_mutations_after_plan: 0
network_calls: 0
provider_calls: 0
```

### 定向回归

Planner、Runtime、任务合同、SSE、六案例、Web UI、认证、附件和 AC-01 图片相关定向集合：

```text
154 passed, 1 skipped
```

全量后端回归：

```text
1956 passed, 15 skipped, 1 warning
```

### 解释规则

Telemetry 的八个控制面计数器是退休门槛的唯一运行时计数来源：

```text
taskrouter_final_route_count
overall_router_rewrite_count
planner_shadow_count
planner_controlled_count
planner_active_count
legacy_runtime_invocation_count
fixed_agent_route_count
fallback_route_count
```

静态 importer 审计与运行时 telemetry 必须同时满足，不能用“代码类仍存在”或“单次测试未触发”替代真实零值证据。

## 6. 未在 Phase N 宣称的内容

- 没有宣称真实模型准确率；
- 没有把 synthetic 案例结果当成真实用户结果；
- 已删除退役的 CT 专用 Solver 配置与代码；
- 没有修改数据库 schema 或公开 Task/RAG/Tool 接口；
- 没有把 Phase P 的组员 Pilot、失败归因和发布交接提前标记为完成。

## 7. 下一阶段边界

Phase N 完成后进入 Phase P：先冻结 Release Candidate snapshot 和真实 Pilot 证据，再做 Critical Bug、Agent Quality、六案例产品化、中文/LaTeX、稳定性/成本和最终交接。Phase P 不再新增 Planner、Runtime、Agent、Memory 架构层。
