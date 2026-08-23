# 芯智导学 Agent Architecture Audit & Refactoring Plan Phase 1

## 1. 审计范围与结论摘要

- 审计对象：2026-08-22 工作树中的 `xinzhi-daoxue`，以当前源码、配置、既有测试和架构文档为事实来源。
- 本阶段只做架构审计和规划，不修改业务代码、API、数据库、Agent 配置或冻结基线。
- 当前系统已经具备可持久化 Runtime、计划、节点、工具/子 Agent 适配、验证、暂停/审批、Checkpoint 和恢复能力；缺口主要不是“没有 Runtime”，而是控制面存在多处路由/意图/上下文/计划边界，导致系统更像“多条 Workflow 拼接 + Runtime 迁移层”，尚未形成单一 Agentic 控制循环。
- 第一优先级不是新增 Agent，而是收敛控制面：统一一次权威的目标理解与路由输入，保留 Runtime Kernel 和业务能力适配器，冻结或合并重复的前置编排。

证据边界：本报告为静态代码/配置/文档审计，没有把已有 Mock、synthetic contract、readiness 或离线评测结果表述为真实 Provider 质量或生产发布证据。

## 2. 当前系统分层

当前实现可以按“入口、控制面、执行面、能力面、持久化/观测面”分层：

| 层 | 当前实现 | 主要事实 |
| --- | --- | --- |
| 入口 | `/api/v1/tasks`、`/api/v1/chat`、LearningLoop 独立入口 | `/tasks` 直接创建非阻塞任务；`/chat` 经过 `XZDSupervisor.prepare()` 后仍复用 `TaskCreationService` 和同一个 Task Executor。 |
| 控制面 | `XZDSupervisor`、`TaskRouter`、`OverallRoutingService`、`FallbackRoutingService`、`RuntimeRequestPreparationService`、`RuntimeLaunchPolicy` | 路由、意图、上下文、Runtime 发布资格分别在多个边界被判断。 |
| Runtime Kernel | `RuntimeRunLifecycleService`、`RuntimeExecutionBoundary`、`RuntimeController`、`PlanExecutor`、`RuntimeStateMachine`、`RuntimePersistenceHooks` | 负责 durable Run、DAG 节点、预算、控制、Checkpoint、事件和恢复。 |
| 业务 Runtime | General Question、Academic Solver、Knowledge QA、Teaching、Research、Generic Goal 等 Runtime service | 业务服务按 Agent ID/选项构建计划并执行；部分服务继承通用问答 Runtime。 |
| 能力面 | `AgentRegistry`、`InternalAgentHub`、`RuntimeHandlerRegistry`、`ToolRegistry`、RAG、Provider | Agent 配置、模型内部 Agent、工具、检索和 Provider 由不同注册/适配层管理。 |
| 数据/观测 | Task/AgentRun/事件表、Session context、Memory、Runtime context、`TraceStore`、`ModelTracer` | 同一任务的路由、计划、节点、结果和会话提交分别落在多个状态容器。 |

## 3. 当前 Agent 控制流图

图例：菱形为决策节点，圆角框为路由/编排节点，矩形为执行节点，圆柱为持久化或观测存储；带 `[重复]` 的节点表示本次审计发现的多次同类判断或状态投影。

```mermaid
flowchart TD
    U[User Input]
    U --> TAPI[POST /api/v1/tasks]
    U --> CAPI[POST /api/v1/chat]

    CAPI --> CPREP[场景/附件/Session 准备]
    CPREP --> SUP[XZDSupervisor.prepare\n课程 + 意图 + 输入规范化]
    SUP --> SR[TaskRouter.route\n[重复路由 #1]]
    SR --> TC[TaskCreationService.create_queued]

    TAPI --> TPREP[场景/附件/Session/上下文准备]
    TPREP --> TR[TaskRouter.route\n[路由 #1]]
    TR --> TC

    TC --> TS[(TaskModel + Task Events + Session Message)]
    TC --> Q[TaskExecutionCoordinator.submit\n非阻塞]
    Q --> LEASE[Task Lease / bounded concurrency]
    LEASE --> RT[TaskRuntimeLifecycle.execute]
    RT --> PREP[TaskRuntimePreparationService.prepare]
    PREP --> RESTORE{是否为 Runtime resume?}
    RESTORE -- 是 --> CP[(AgentRun checkpoint / compatibility snapshot)]
    RESTORE -- 否 --> CTX1[ContextAssemblyService\n上下文组装 #1]
    CTX1 --> OR{OverallRoutingService\n是否需要模型路由?}
    OR -- 不调用 --> FQ{FallbackRoutingService\n是否需要兜底?}
    OR -- 调用 --> ORR[Overall route refinement\n[重复路由 #2]]
    ORR --> CTX2[ContextAssemblyService\n因路由变化重组 #2]
    CTX2 --> FQ
    FQ -- 调用 --> FR[Fallback route refinement\n[重复路由 #3]]
    FR --> CTX3[ContextAssemblyService\n因兜底变化重组 #3]
    FQ -- 不调用 --> PLAN
    CTX3 --> PLAN
    PLAN[AgentExecutionPlanner + IntentPlanCompiler\n生成/绑定执行计划]
    PLAN --> LP[RuntimeLaunchPolicy\n发布/模式/资格决策]
    LP --> RP[RuntimeBusinessRegistry.resolve\n选择业务 Runtime]
    RP --> RPLAN[业务 Runtime build_plan\n或 Legacy compatibility plan]
    RPLAN --> START[RuntimeRunLifecycle.start_or_restore]
    START --> CP

    CP --> BOUND[RuntimeExecutionBoundary.execute]
    BOUND --> SERVICE{Runtime service / Legacy handler}
    SERVICE --> CTRL[RuntimeController\nobserve → decide → act → verify]
    CTRL --> EXEC[PlanExecutor\n节点/DAG/预算/审批/暂停/恢复]
    EXEC --> H[Tool / RAG / Provider / InternalAgentHub]
    H --> OBS[(RuntimeObservation / Decision / Node State)]
    OBS --> CTRL
    CTRL --> RES[AgentResult]
    RES --> GOV[RuntimeResultPipeline\n输出契约/质量门/场景校验]
    GOV --> VERIFY{结果是否可发布?}
    VERIFY -- 否 --> FAIL[(Task failed + error/event)]
    VERIFY -- 是 --> COMMIT[TaskCompletionService.commit]
    COMMIT --> FINAL[(Task + AgentRun + Session + Result + Events)]
    COMMIT --> POST[Post-processing\n记忆摘要/研究摄取/学习状态]
```

### 3.1 旧协议 `/chat` 路径

`POST /api/v1/chat` 和 `/chat/stream` 在 `orchestration.py` 中先构造/获取 Session、检查附件，然后调用 `XZDSupervisor.prepare()`。Supervisor 内部完成课程识别、意图识别、输入类型识别、legacy `AgentRequest` 转换、`TaskRouter.route()`、本地知识优先和多图/PDF 本地兜底；之后调用的仍是同一 `TaskCreationService.create_queued()` 与 `TaskExecutionCoordinator`。因此 Supervisor 不是一条独立执行链，但它是第二个前置控制面。

### 3.2 任务 API `/tasks` 路径

`POST /api/v1/tasks` 直接做场景绑定、附件水合、SessionContext 投影、条件性的上下文组装，然后调用 `TaskRouter.route()`。`TaskCreationService` 将路由决定写入 Task，编译 `IntentExecutionPlan`，写入路由/意图/计划/技能/工具事件，并以 `202 Accepted` 后提交后台执行。任务创建没有直接调用 Provider，满足“非阻塞创建”边界。

### 3.3 Runtime 执行路径

后台执行先由 Coordinator 获取 lease，再由 `TaskRuntimePreparationService` 锁定 Task、恢复请求、标记运行、决定是否恢复已有 Run，并把最终请求交给 `RuntimeRequestPreparationService`。新任务可能经历 Overall route refinement 和 Fallback routing；如果目标改变，代码会更新 Task 的 agent/course/intent，并重建上下文与意图计划。随后 Runtime Launch Policy 决定 default/canary/legacy 兼容模式，Runtime Business Registry 解析业务 Runtime，Boundary 创建或恢复 AgentRun，最后由业务 Runtime、Controller、Executor、Handler/Provider 完成执行。

结果不会因为 Runtime Run 完成就直接发布：`TaskRuntimeExecutionService` 先经过 `RuntimeResultPipeline`，再由 `TaskCompletionService` 做 terminal guard、结果呈现、Session 提交、AgentRun/Result 持久化和终态事件。

## 4. 决策点、路由点、执行点、存储点清单

| 类型 | 当前节点 | 输入/输出 | 审计判断 |
| --- | --- | --- | --- |
| 决策 | `IntentRecognitionService`、Supervisor `_course/_intent`、TaskRouter scoring | 文本、课程/意图提示、附件、Session continuity → 课程/意图/候选 Agent | 同类“目标理解”分散，权威性不清。 |
| 路由 | `TaskRouter.route()` | `AgentRequest` → `RouteDecision` | 入口创建时至少一次；Runtime 准备阶段还可能由 Overall/Fallback 改写。 |
| 路由 | `OverallRoutingService.route()` | 当前决定 + 候选目录 → 结构化模型 route | 是第二个模型路由器，不应长期与 Planner 并存为平行权威。 |
| 路由 | `FallbackRoutingService.resolve()` | 当前决定 + Provider 状态 → fallback route | 是可用性/降级策略，建议保留为 Policy，而不是继续发展成独立 Planner。 |
| 决策 | `RuntimeLaunchPolicy` | Agent、Runtime option、版本/evidence → launch mode | 发布门禁与任务路由耦合在准备阶段，需保持 fail-closed。 |
| 计划 | `IntentPlanCompiler`、`AgentExecutionPlanner`、各 Runtime `build_plan()`、`RuntimeGoalPlanner` | route/goal/capabilities → 多种 plan 合同 | 计划模型存在多个方言；后续应统一 canonical plan，而不是再加一种。 |
| 执行 | Coordinator、`TaskRuntimeLifecycle`、Boundary、Controller、Executor | Task/AgentRun → Provider-free 或真实能力执行 | Runtime Kernel 是核心基础设施，应保留。 |
| 执行 | `InternalAgentHub`、`ToolRegistry`、RAG、Provider | typed request → structured result/evidence | 适配边界较清晰，但内部 Agent 既承载业务生成又承载路由/整理。 |
| 验证 | Runtime verification、`RuntimeResultPipeline`、Agent result validators、场景/solver quality gate | Run/Result → 可发布或失败 | 具备多层校验，但缺少统一 Critic → Revision 语义。 |
| 存储 | Task/AgentRun/Events/Session/RuntimeContext/Memory/TraceStore/ModelTracer | 状态、事件、上下文、记忆、模型调用 → 持久化/观测 | 状态源较多，需明确 canonical owner。 |

## 5. 重复功能与复杂度来源

### 5.1 多次任务/意图判断

当前至少存在以下判断链：

1. 场景自动绑定使用 `IntentRecognitionService` 将若干 intent 映射到 showcase scenario；
2. `/chat` 的 `XZDSupervisor` 自己识别课程和意图；
3. `TaskRouter.route()` 再次调用 `IntentRecognitionService`，并执行 legacy rules/scoring；
4. Runtime 准备阶段可调用 `OverallRoutingService` 做模型二次路由；
5. 某些不满足条件的任务再进入 `FallbackRoutingService`。

这些步骤各自有合理局部目的，但缺少一个稳定的“目标理解快照”。结果是路由决定可能在 Task 创建后变化，虽然当前代码通过 `route_reevaluated`、compatibility snapshot 和事件记录保留可追溯性，但成本是额外上下文、额外延迟和更多状态分叉。

### 5.2 重复上下文组装

- `/tasks` 在路由前可先使用 `ContextAssemblyService` 为 router 构造上下文；
- `TaskCreationService` 又执行 `SessionContextService.apply()`；
- Runtime 准备阶段重新组装执行上下文；
- Overall/Fallback route 改变目标后会再次组装上下文；
- `SessionCompactionService` 和 `PostProcessing` 又异步生成/保存摘要。

这不是简单的“全部删掉”：路由上下文与执行上下文可能需要不同预算。但当前接口没有清晰区分 `RoutingContext`、`ExecutionContext` 和 `ExperienceContext`，导致同一个 `options` 字典成为跨层临时总线。

### 5.3 重复状态管理

同一用户任务同时经历：Supervisor `XZDGraphState`、TaskModel 状态、Task events、AgentRun/Runtime state machine、Session context、Runtime context summary，以及 Memory/Learning state。事件记录和 durable Run 是必要的；问题在于部分状态（route、plan、agent、progress、verification）存在多个投影，尚未声明谁是事实源、谁是只读投影。

### 5.4 计划方言并存

当前同时存在 `IntentExecutionPlan`、`AgentExecutionPlan`、`AgentRunPlan`、业务 Runtime 自建 plan 和 Generic Goal `RuntimeGoalPlanner` 输出。`IntentPlanCompiler.to_runtime_plan()` 已经提供迁移适配，但 `RuntimeRequestPreparation`、业务 Runtime 和 Generic Goal 仍分别拥有计划决策逻辑。建议下一阶段只收敛为：一个 `Goal/Plan` canonical contract + 面向旧 API 的兼容适配器。

## 6. 当前架构审计判断

| 维度 | 结论 | 依据 |
| --- | --- | --- |
| 是否已经具备 Agentic Runtime | 部分具备 | Runtime 已有 observe/decide/act/verify、bounded replan、tool/subagent adapter、Checkpoint 和 recovery contract；但业务入口仍由多套前置路由/计划编排驱动。 |
| 是否存在“多 Agent 就是多智能” | 存在误差 | Agent Registry、InternalAgentHub、Runtime service 和 Generic Goal 都可以声明能力，但目前主要按固定 Agent ID/意图分流，技能/经验没有成为统一的选择依据。 |
| 最大复杂度 | 控制面重复 | 入口 Supervisor、TaskRouter、Overall Router、Fallback Router 与 Runtime Preparation 都能改变最终目标。 |
| 最稳定的核心 | Runtime Kernel + contracts + persistence | 该部分承担恢复、状态、预算、事件、发布门禁和结果边界，属于系统可靠性基础。 |
| 最适合收敛的对象 | 前置路由、上下文、计划编译 | 这些边界当前重叠最多，也最适合作为后续 Planner/Skill/Memory 的落点。 |

## 7. 初步收敛方向

- 把 `TaskRouter` 限定为 deterministic preflight/compatibility adapter，短期保留 API 兼容；不再向其中添加新的智能分解逻辑。
- 把 `OverallRoutingService` 视为 Planner 引入前的过渡 refinement；Phase B 由 `PlannerService` 统一 goal understanding、decomposition、Agent/Skill/Tool selection 后再决定其去留。
- 保留 `RuntimeExecutionBoundary`、`RuntimeController`、`PlanExecutor`、`RuntimeStateMachine`、`RuntimeBusinessRegistry` 和 durable persistence；它们是执行底座而不是重复 Agent。
- 保留 Academic Solver 作为业务能力边界和 `SOLVER_CT v1.0` 兼容层；先用 capability/skill 扩展，不拆成更多课程 Agent。
- 把 Session/Working State/Learning State/Memory 先区分为短期上下文、学习状态和用户显式记忆；Phase E 再新增经验证的 Experience Memory，避免把当前 Memory 表直接改造成策略库。

## 8. 本报告证据入口

- API 入口与非阻塞任务：`apps/api/app/api/v1/tasks.py`、`apps/api/app/api/v1/orchestration.py`
- Supervisor：`apps/api/app/orchestrator/supervisor.py`
- Task 路由：`apps/api/app/agents/router.py`、`apps/api/app/agents/registry.py`
- Runtime 准备/执行/提交：`apps/api/app/services/task_runtime_preparation.py`、`apps/api/app/services/runtime_request_preparation.py`、`apps/api/app/services/task_runtime_execution.py`、`apps/api/app/services/task_completion.py`
- Runtime Kernel：`apps/api/app/runtime/contracts.py`、`apps/api/app/runtime/controller.py`、`apps/api/app/runtime/executor.py`、`apps/api/app/services/runtime_execution_boundary.py`
- Runtime 业务注册：`apps/api/app/bootstrap/runtime_task_engine.py`、`apps/api/app/services/runtime_business_registry.py`
- 既有边界说明：`docs/architecture/agent_runtime_foundation.md`、`docs/evaluation/runtime_true_agent_contract_matrix.md`
