# Runtime 能力盘点与迁移边界

> 盘点时间：2026-08-09
>
> 本文只记录当前仓库可由代码、配置和现有架构文档核实的事实，并给出后续迁移的可验收边界。它不是新的运行时协议，也不授权改变现有路由、任务协议或冻结基线。

## 1. 结论摘要

当前仓库存在两条合法但尚未完全汇合的执行入口：

1. **Task Agent Runtime** 面向可路由的 Agent 工作流。请求是 `AgentRequest`，入口是 `POST /api/v1/tasks`；任务创建保持非阻塞，随后由 `TaskRunner` 根据 launch policy 选择 Legacy、Shadow、Canary 或 Default Runtime，Runtime 计划由 `RuntimeBusinessRegistry` 提供。
2. **LearningLoop** 面向学习领域动作。请求是 `LearningActionRequest`，入口是 `POST /api/v1/learning/actions`；`LearningLoopService` 决定进入传统学习领域服务，或进入 `TeachingInteractionRuntimeService` / `LearningProgressRuntimeService`。这些动作不是普通的聊天任务，不应为了“统一”而伪装成 `AgentRequest`。

目标不是把两个领域协议强行合并，而是让它们共享同一套可持久化 Runtime 内核、计划/节点/观察/决策/验证/控制语义、审计事件和 readiness 投影。学习域仍保留 `LearningActionRequest` 及其领域结果合同；Task 域仍保留 `AgentRequest`、Task 和 SSE 合同。

## 2. 事实来源与稳定边界

以下路径是本盘点的直接事实来源：

| 事实 | 来源 |
| --- | --- |
| Task 创建、路由、非阻塞提交 | `apps/api/app/api/v1/tasks.py:102`；`apps/api/app/api/v1/tasks.py:140` |
| TaskRunner 的 Runtime 执行与任务结果交接 | `apps/api/app/services/task_runner.py:346`；`apps/api/app/services/task_runner.py:676-766` |
| 统一 Runtime Business Registry 的服务解析、计划和 option key | `apps/api/app/services/runtime_business_registry.py:15-128` |
| RuntimeExecutionBoundary 将业务服务装入 Registry | `apps/api/app/services/runtime_execution_boundary.py:75-90` |
| Agent ID、版本、入口模式和 Legacy local handler | `agent_configs/registry.yaml:22-717` |
| 路由候选 Agent、意图到 Agent 的映射 | `apps/api/app/agents/router.py:22-107` |
| 每个已注册 Agent 的 Runtime readiness | `apps/api/app/services/runtime_agent_readiness.py:67-303`；`apps/api/app/api/v1/agents.py:109-126` |
| Task Runtime pause/resume/approve/input 控制 | `apps/api/app/api/v1/tasks.py:379-440` |
| 学习动作独立入口与学习 Runtime 审批入口 | `apps/api/app/api/v1/learning.py:33-67` |
| LearningLoop capability descriptor 的字段与 provider-free 构造 | `apps/api/app/services/runtime_capability_descriptor.py:50-113,182-284`；`apps/api/app/main.py:346-365` |
| LearningLoop `agent_version` 显式身份声明 | `e883606`；`apps/api/app/services/teaching_interaction_runtime.py:53-59`；`apps/api/app/services/learning_progress_runtime.py:60-66`；`apps/api/tests/test_runtime_capability_descriptor.py` |
| LearningLoop readiness 投影及版本/canary 字段 | `apps/api/app/contracts/learning.py:479-513`；`apps/api/app/api/v1/learning.py:223-275,408-504` |
| LearningLoop readiness 的显式版本与 fail-closed 测试 | `apps/api/tests/test_learning_runtime_readiness_api.py`；`apps/api/tests/test_learning_runtime_release_readiness.py` |
| canary artifact/semantic evidence 的版本绑定与发布门禁 | `apps/api/app/services/runtime_canary_release.py:20-149`；`docs/evaluation/runtime_evidence_intake_contract.md`；`docs/evaluation/runtime_authorized_paired_trace_release_runbook.md` |
| LearningLoop 的 Legacy/Teaching/LearningProgress 分流 | `apps/api/app/services/learning_loop.py:91-190` |
| TeachingInteractionRuntime 的 ID、计划节点、请求快照和审批 | `apps/api/app/services/teaching_interaction_runtime.py:42-146` |
| LearningProgressRuntime 的 ID、计划节点、请求快照和审批 | `apps/api/app/services/learning_progress_runtime.py:51-153` |
| 两类学习动作及领域字段 | `apps/api/app/contracts/learning.py:373-409` |
| `AgentRequest` 的 Task/Provider 基础协议 | `apps/api/app/contracts/agent.py:235-254` |
| SOLVER_CT v1.0 冻结约束 | `docs/baseline/solver_ct_v1.0_baseline.md:1-18`；`AGENTS.md` 项目规则 |

## 3. 两条入口的边界

### 3.1 Task Agent Runtime

```text
AgentRequest
  -> POST /api/v1/tasks
  -> TaskCreationService.create_queued()
  -> TaskExecutor.submit()
  -> TaskRunner
  -> RuntimeLaunchPolicy
  -> RuntimeExecutionBoundary
  -> RuntimeBusinessRegistry / Provider / Legacy local handler
```

其职责是执行可路由的任务型 Agent：生成目标和计划、持久化 `AgentRun`、推进节点、调用受控工具/Provider/子 Agent、记录事件、处理暂停/恢复/审批/输入、完成结果交接。统一 readiness 以 `agent_configs/registry.yaml` 中的 Agent ID 为主键，通过 `GET /api/v1/agents/runtime-readiness` 暴露。

### 3.2 LearningLoop

```text
LearningActionRequest
  -> POST /api/v1/learning/actions
  -> LearningLoopService.act()
  -> TeachingInteractionRuntimeService 或 LearningProgressRuntimeService
     （未启用/不支持时回到对应领域 Legacy service）
  -> LearningInteractionModel / LearningActionResponse
```

其职责是处理学生动作、教学反馈、尝试修订、重测和掌握度副作用。它使用 `source_task_id` 关联来源 Task，但这不等于学习动作本身是一个 `AgentRequest`。学习动作的幂等键、学生答案、动作类型、学习结果和领域审批语义属于 `LearningActionRequest` / `LearningActionResponse`。

Teaching 和 LearningProgress Runtime 已经复用了 `AgentRun`、Runtime plan/node/checkpoint、事件和控制器，但它们当前是 LearningLoop 的专用服务：

- `TeachingInteractionRuntimeService.agent_id = TEACHING_INTERACTION_V1`；支持 `request_more_hint`、`submit_check_response`、`switch_to_direct_answer`。
- `LearningProgressRuntimeService.agent_id = LEARNING_PROGRESS_V1`；支持 `submit_attempt_revision`、`start_retest`、`complete_retest`、`dismiss_retest`。
- 两者的请求快照均保存为 `request_snapshot["learning_action"]`，并由学习域服务完成最终领域副作用。
- 两者均有自己的 `approve()`，但入口是 `/api/v1/learning/runtime/{run_id}/approve`，不是 Task Runtime 的统一 Agent readiness/control 面。

## 4. Agent ID 与入口盘点

### 4.1 `agent_configs/registry.yaml` 中的正式 Agent

| Agent ID | 当前主入口/事实模式 | RuntimeBusinessRegistry | 统一 readiness/control | 当前判断 |
| --- | --- | --- | --- | --- |
| `DISPATCH_LOCAL_FAST_V1` | 路由快速分发，`routing_only` | 否 | readiness 可列出，但无业务 Runtime 计划 | 路由基础设施，不应直接迁移为业务 Agent |
| `ROUTER_01_FALLBACK_V1` | `XZDSupervisor`，`routing_only` | 否 | readiness 可列出，但无业务 Runtime 计划 | 路由基础设施，不应作为业务 Runtime 节点执行 |
| `ACADEMIC_PROBLEM_SOLVER` | 本地图与 Solver 适配 | 是：`AcademicSolverRuntimeService` | 是，受 launch policy/release gate 约束 | 已进入 Task Runtime |
| `SOLVER_CT_V1` | Xingchen/冻结 CT 基线，受控回退/比较 | 否 | 作为 Agent 状态存在，但不纳入新 Runtime 迁移 | **冻结，不修改、不重写、不接学习动作** |
| `LEARN_01_KNOWLEDGE_QA_V1` | Provider/本地知识问答 | 否；其本地检索 Runtime 对应另一个 ID | readiness 有 Agent 条目，但该 ID 没有直接 Runtime plan | 仍需明确 Provider 兼容路径与 Runtime 计划的关系 |
| `LEARN_01_LOCAL_RETRIEVAL_V1` | 本地检索/知识问答 | 是：`KnowledgeQARuntimeService` | 是 | 已进入 Task Runtime，但与 Provider QA ID 分离 |
| `GENERAL_QUESTION_V1` | 本地一般问题服务 | 是：`GeneralQuestionRuntimeService` | 是 | 已进入 Task Runtime |
| `TEACH_01_LESSON_PREP_V1` | 教学备课 | 是：`LessonPrepRuntimeService` | 是 | 已进入 Task Runtime |
| `TEACH_02_ASSIGNMENT_REVIEW_V1` | 作业评阅 | 是：`AssignmentReviewRuntimeService` | 是 | 已进入 Task Runtime |
| `RESEARCH_01_ACADEMIC_SEARCH_V1` | `ResearchFrontierService` 外部研究 | 是：`ExternalResearchRuntimeService` | 是 | 已进入 Task Runtime，外部检索仍受自身策略和配置约束 |
| `RESEARCH_02_ACADEMIC_WRITING_V1` | 学术写作 | 是：`AcademicWritingRuntimeService` | 是 | 已进入 Task Runtime |
| `RESEARCH_03_DATA_ANALYSIS_V1` | 研究数据分析 | 是：`ResearchAnalysisRuntimeService`，由 `RuntimeExecutionBoundary` 单独注入 | 是 | 已进入 Task Runtime，但仍存在 TaskRunner 中的兼容分支 |

### 4.2 LearningLoop 专用 Runtime ID 与 readiness 投影

| Runtime ID | 领域服务/计划版本来源 | 是否在 `agent_configs/registry.yaml` | 是否在 `RuntimeBusinessRegistry` | readiness 投影与当前证据 | 当前判断 |
| --- | --- | --- | --- | --- | --- |
| `TEACHING_INTERACTION_V1` | `TeachingInteractionRuntimeService.agent_version = learning-agent-v1`；`plan_version = teaching-interaction-v1`；descriptor 将二者分别投影 | 否 | 否 | `GET /api/v1/learning/runtime-readiness` 可列出；返回 `agent_version`、`runtime_plan_version`、`canary_release_eligible`、`canary_reason`；当前无授权 evidence，故 canary 仍为 false | Runtime DAG 与 capability identity 已实现，仍未完成正式 Agent Registry 接入，也未授权 canary/default |
| `LEARNING_PROGRESS_V1` | `LearningProgressRuntimeService.agent_version = learning-agent-v1`；`plan_version = learning-progress-v1`；descriptor 将二者分别投影 | 否 | 否 | 同上；版本身份已显式声明，但不能替代 authorized evidence | Runtime DAG 与 capability identity 已实现，默认配置仍受 feature flag/证据门禁约束 |

这里的 `runtime_plan_version` 是当前可核验的计划版本；它不是 `agent_version` 的替代品。`RuntimeCapabilityDescriptor` 已包含 `agent_version`，两个真实 LearningLoop service 均显式声明 `learning-agent-v1`，descriptor builder 和 readiness API 分别保留两个身份字段。`_project_learning_runtime_descriptor()` 仍只读取 descriptor 明确提供的值，不从 canary artifact 或 plan version 推断。现有真实 descriptor 测试证明身份投影成立；没有 authorized evidence 时，release registry 仍返回 `canary_release_evidence_missing` 并保持 fail-closed。

## 5. 当前统一程度与缺口

### 已统一的部分

- 两条路径都可以使用持久化 `AgentRun`、Runtime plan/node、checkpoint、状态版本、观察/决策/验证事件和人工审批状态。
- Task Runtime 有 `RuntimeBusinessRegistry`、launch policy、readiness、pause/resume/approve/input 和调试执行面。
- LearningLoop 的两个专用 Runtime 已把学习领域动作放入可恢复的 Runtime DAG，并保留领域服务作为副作用执行器；学习 API 路由本身不直接调用 Provider。

### 尚未统一的部分

- `TEACHING_INTERACTION_V1` 和 `LEARNING_PROGRESS_V1` 仍不在 `RuntimeBusinessRegistry`，因此不会被 `RuntimeAgentReadinessService` 作为正式 Task Agent 评估，也不会出现在 `/api/v1/agents/runtime-readiness` 的 Agent 清单中；它们现在通过独立的 `/api/v1/learning/runtime-readiness` 只读投影暴露。
- LearningLoop readiness 已有 typed contract 字段 `agent_version`、`runtime_plan_version`、`canary_release_eligible`、`canary_reason`；真实 descriptor 已显式声明 `learning-agent-v1`，并复用共享 `RuntimeCanaryReleaseRegistry` 做 provider-free 检查。但当前仍没有 authorized evidence；readiness 字段不是授权，也不替代 `authorized_paired` structural suite、semantic sidecar 或独立发布审批。
- Task 的通用 pause/resume/approve/input 控制面与 LearningLoop 的专用 approve 仍不是同一个业务 API 合同；学习 Runtime 有独立的 controls 投影和 control 入口，但 pause/resume/input 仍显式拒绝。
- Task readiness 的主键仍来自 Agent Registry；LearningLoop 的 descriptor 只读投影不改变 `LearningActionRequest` 或领域 `supports()` 语义。
- TaskRunner 仍保留若干业务兼容分支，即使对应 Runtime service 已存在；是否迁移完成不能只看是否创建了 Runtime 类，必须看默认/Canary 入口、结果交接和 Legacy 分支是否有证据。
- LearningLoop 的 Runtime 结果仍需要以 `LearningActionResponse` 和 `LearningInteractionModel` 完成领域交接，不能直接复用 Task 的通用结果展示合同。

## 6. 目标架构：统一内核，分离领域协议

### 6.1 必须保持的两个边界

1. **不改变请求协议归属**：Task 继续接收 `AgentRequest`；学习动作继续接收 `LearningActionRequest`。学习动作不能为了接入统一 Runtime 而硬接到 `AgentRequest`，也不能通过伪造 `agent_id` 绕过学习领域的用户、来源 Task、幂等和领域校验。
2. **不改变结果协议归属**：Task 继续通过 Task/SSE/AgentResult 交接；学习动作继续通过 LearningActionResponse/LearningInteractionModel 交接。共享的是 Runtime 生命周期和审计语义，不是把两个业务结果合同抹平。

### 6.2 当前能力投影与剩余统一方式

仓库已经有 provider-free 的 `RuntimeCapabilityDescriptor` 和 LearningLoop readiness 投影。当前已声明/可观察的字段包括：

- 稳定 capability/runtime ID 与版本；
- 所属域（Task Agent 或 LearningLoop）；
- 输入适配器类型（`AgentRequest` 或 `LearningActionRequest`）；
- plan version、节点和副作用边界；
- 是否支持 pause/resume/input/approval；
- readiness、canary、默认发布所需的证据字段；LearningLoop readiness 还暴露 `agent_version`、`runtime_plan_version`、`canary_release_eligible`、`canary_reason`；
- 领域结果交接器与失败/回退策略。

该投影层可以让 Operator 使用统一的 readiness/control 视图，但不要求 LearningLoop 服务实现 `RuntimeBusinessService` 的 `AgentRequest` 签名。LearningLoop 的 `agent_version` 来源现已在服务和 descriptor 中明确；剩余门槛是让授权 paired evidence 与 `agent_version`/`runtime_plan_version` 严格绑定，在此之前不得把 readiness 的 canary 字段解释为已授权发布。

## 7. 分阶段迁移与验收条件

### 阶段 0：冻结清单与协议

**范围**：固定本文表格、ID、入口、运行模式和“不修改项”。

**验收**：

- Agent Registry ID、Learning Runtime ID、Task API、Learning API 和来源路径均可逐项追溯；
- `SOLVER_CT v1.0`、其原始 YAML、Provider 凭据和现有 Task/SSE 合同没有变更；
- 测试能证明学习动作仍由 `LearningActionRequest` 接收，且没有通过 `AgentRequest` 路由进入 Task。

### 阶段 1：建立跨域能力描述，不迁移执行

**范围**：为 Task Runtime 和两个 Learning Runtime 提供只读 descriptor；保持两个请求/结果合同和现有入口不变。

**验收**：

- descriptor 能明确区分 `task_agent` 与 `learning_loop`；
- 每个 descriptor 能报告 runtime ID/version、计划版本、支持动作/能力、控制能力、enabled 状态和领域交接器；LearningLoop 真实 descriptor 还显式报告 `agent_version=learning-agent-v1`；
- 缺少 descriptor 或版本不匹配时，readiness 明确阻断，不自动提升为 Default；
- provider-free 测试覆盖全量 Agent Registry 与两个 Learning Runtime。

**当前证据**：descriptor 构造、main wiring、两个 service 的 `agent_version` 声明、readiness API 和 provider-free 测试均已存在；授权 evidence 仍未完成。

### 阶段 2：统一 readiness/control 投影

**范围**：把 Learning Runtime descriptor 纳入只读 readiness 与控制面投影；不把学习动作改成 `AgentRequest`。

**验收**：

- Operator 可以通过独立 readiness/status/control 投影看到 Learning Runtime 的版本、动作、控制能力、canary reason 和阻塞原因；该投影不等于 Agent Registry 条目或发布授权；
- pause/resume/approval/input 权限、用户身份、状态版本和 ownership 校验在两个域中语义一致；
- 控制请求只改变 Runtime 状态和领域允许的控制数据，不直接执行 Provider，不跳过 LearningLoop 领域校验；
- SSE/学习事件的顺序、重连和幂等测试不回归。

**当前证据**：`test_learning_runtime_readiness_api.py`、`test_learning_runtime_release_readiness.py` 证明投影 provider-free、域过滤、真实 descriptor 的显式版本读取、共享 release registry 查询和缺失版本时 fail-closed；未证明真实 paired trace 或生产 canary。

### 阶段 3：TeachingInteraction canary

**范围**：只迁移已由 `TeachingInteractionRuntimeService` 覆盖的三个动作，继续由 LearningLoop 负责请求解析、领域副作用和结果持久化。

**验收**：

- 每个动作都有 Legacy 与 Runtime 的授权 paired trace，输入哈希一致，结果按学习领域语义比较；
- Runtime 失败、暂停、审批超时或验证失败时，不能写成已完成的学习交互；
- canary 期间默认仍 fail closed，未获得版本、结构和语义证据不得 Default；
- 教学提示、直接回答、检查反馈的领域安全规则和答案披露策略不回归。

### 阶段 4：LearningProgress canary

**范围**：迁移四个 phase-3 学习动作，保留 `LearningOutcomeService`/重测规则作为领域执行器，Runtime 负责可恢复编排和验证。

**验收**：

- 尝试修订、开始/完成/取消重测分别有幂等、状态迁移、掌握度和重测计划的 paired trace；
- Runtime 的 observe/apply/verify 顺序可审计，副作用 effect key 可重放或可证明已提交；
- 学习记录、来源 Task 归属和用户隔离测试通过；
- 任何未授权或不完整证据都只能保持 Legacy/Canary/blocked，不得自动 Default。

### 阶段 5：逐项减少 TaskRunner/学习 Legacy 分支

**范围**：以 capability 为单位迁移，而不是整体重写。每项能力只有在 Runtime 默认路径稳定后，才减少对应 Legacy 分支；`SOLVER_CT_V1` 始终排除在本阶段之外。

**验收**：

- Runtime 与 Legacy 的结果交接、失败回退、暂停恢复、审计和指标均有回归测试；
- 删除或收窄分支前，有对应 release artifact、版本绑定、结构 gate 和语义证据；
- Task 与 LearningLoop 的入口协议仍各自稳定，跨域调用只通过显式适配器；
- 全量 Ruff/Mypy/Pytest、配置检查、敏感文件扫描和协议顺序/重连测试通过；未执行的 Provider、Docker 或外部服务验证必须单独标注。

## 8. 明确禁止的捷径

- 不把 `LearningActionRequest` 塞入 `AgentRequest.options`，不把学习动作伪装成聊天任务，不用 `source_task_id` 代替学习领域身份/幂等校验。
- 不因 Teaching/LearningProgress 已创建 `AgentRun` 就把它们标成已进入统一 `RuntimeBusinessRegistry` 或统一 Agent readiness。
- 不在 TaskRunner 中直接执行学习 Provider；学习 Runtime 的领域副作用仍由 LearningLoop 及其注入的领域执行器承担。
- 不修改 `SOLVER_CT v1.0`、`SOLVER_CT_V1` 的冻结实现、原始星辰 YAML、Flow ID 或真实凭据；只能做只读适配、hash/parity 和受控回退验证。
- 不用一次成功的本地 Mock 或单条 trace 宣称完成迁移；必须有授权、可复现、成对、版本绑定的结构与语义证据。

## 9. 维护规则

每次新增 Agent、Runtime service、学习动作或入口时，同一变更必须更新本盘点对应表格，并补充：事实来源路径、输入/结果合同、Registry/readiness/control 状态、Legacy 分支、版本和验收证据。若只实现了 Runtime 类而未完成注册、控制、结果交接或证据，不得把状态写成“已迁移”。

## 10. Control projection checkpoint

跨入口 descriptor 和 LearningLoop status/control 投影共享 provider-free、
fail-closed 的控制策略。Task Runtime 默认声明 pause/resume/approval/input；
LearningLoop 目前只在 `waiting_approval` 暴露 `approve`。未知 Runtime kind、
不支持状态和终态不暴露控制动作。该策略只说明“可显示/可请求的控制能力”，
不替代现有后端对 ownership、用户身份、state version、持久化和领域结果提交的
校验。

LearningLoop 已提供：

- `GET /api/v1/learning/runtime/{run_id}/controls`：读取当前可用控制；
- `POST /api/v1/learning/runtime/{run_id}/control`：`approve` 委托现有领域审批；
- `pause`、`resume`、`input`：审计并拒绝，`provider_called=false`。

因此“有 approval 控制”应记录为已实现的控制合同；“有完整暂停/恢复/输入控制”仍是未实现能力。

## 11. LearningLoop readiness checkpoint

`GET /api/v1/learning/runtime-readiness` 是两个 LearningLoop Runtime capability
的独立、provider-free 只读投影。当前可核验字段如下：

| 字段 | 代码来源/含义 | 当前真实状态 | 不能据此推出 |
| --- | --- | --- | --- |
| `capability_id` / `runtime_id` | descriptor 与两个 Runtime service 的稳定 ID | `TEACHING_INTERACTION_V1`、`LEARNING_PROGRESS_V1` 可投影 | 已进入 Agent Registry 或可路由 |
| `version` | `RuntimeCapabilityDescriptor.version`，由学习服务的 `plan_version` 读取 | `teaching-interaction-v1` / `learning-progress-v1` | 这是 Agent 发布版本 |
| `runtime_plan_version` | readiness 投影优先读取 descriptor 的同名字段，否则回退到 `version` | 当前真实 descriptor 通过回退得到计划版本 | 已绑定真实 Agent artifact |
| `agent_version` | 只读取 descriptor 明确声明的同名字段 | 两个真实 LearningLoop descriptor 均为 `learning-agent-v1` | 该字段仍不能替代 authorized evidence，不能由 artifact 反向授权 |
| `canary_release_eligible` | 调用共享 `RuntimeCanaryReleaseRegistry.release_eligible()`，不执行 Provider | 当前为 `false`：`learning-agent-v1`/plan 版本已声明，但 registry 没有授权 evidence | readiness 本身不是 canary/default 授权 |
| `canary_reason` | 共享 release registry 的结构/语义/版本阻塞原因，或版本 expectation 缺失 | 当前真实 descriptor + 空 registry 为 `canary_release_evidence_missing`；缺失版本的负向测试仍为 `canary_artifact_version_expectation_missing` | 不是质量分数，也不是实际执行结果 |
| `blockers` | API 投影的控制、enabled 和 authorized paired evidence 阻塞项 | 包含 pause/resume/input 未实现及 `learning_runtime_authorized_paired_evidence_missing` 等 | 不能把 synthetic/Mock 测试变成真实证据 |

测试证据：`test_learning_runtime_readiness_api.py` 验证域过滤、字段投影、provider-free
行为与 approve-only 控制事实；`test_learning_runtime_release_readiness.py` 验证显式
`agent_version` 可被读取、共享 release registry 会被查询，以及缺失 Agent version
不会从 artifact 推断。它们都是 contract/synthetic evidence，不是发布证据。

## 12. LearningLoop 后续迁移证据矩阵

状态含义固定为：

- **实现**：代码路径和局部合同存在；
- **可评测**：有可重复的 provider-free/结构测试或离线门禁输入合同；
- **已授权**：有版本绑定的真实 `authorized_paired` Legacy/Runtime trace、独立 semantic sidecar 和发布审批。只有这一列成立才可进入 canary/default 决策。

| 能力/动作 | 实现证据 | 可评测证据 | 已授权证据 | 当前结论/下一门槛 |
| --- | --- | --- | --- | --- |
| `TEACHING_INTERACTION_V1` descriptor 与版本身份 | `runtime_capability_descriptor.py:182-284`；`teaching_interaction_runtime.py:53-59`；`main.py:351-365` | `test_runtime_capability_descriptor.py`、`test_learning_runtime_readiness_api.py`、`test_learning_runtime_release_readiness.py` | 无 authorized paired suite | **实现、可评测**；版本身份已完成，下一门槛是授权结构 suite |
| Teaching `request_more_hint` / `submit_check_response` / `switch_to_direct_answer` | `teaching_interaction_runtime.py:70-75,145-180`；`learning.py:83-105` | Runtime/approval contract tests；只证明注入的本地领域执行器 | 无；仓库没有该能力的授权 Legacy/Runtime trace | **实现、可局部评测**；需同输入 paired trace、领域语义审查和回滚记录 |
| `LEARNING_PROGRESS_V1` descriptor 与版本身份 | `runtime_capability_descriptor.py:193-222,233-284`；`learning_progress_runtime.py:60-66`；`main.py:341-365` | `test_runtime_capability_descriptor.py`、`test_learning_runtime_readiness_api.py`、`test_learning_runtime_release_readiness.py` | 无 authorized paired suite | **实现、可评测**；版本身份已完成，下一门槛是授权结构 suite |
| LearningProgress `submit_attempt_revision` / `start_retest` / `complete_retest` / `dismiss_retest` | `learning_progress_runtime.py:77-83,152-187`；`learning.py:83-95` | Runtime/领域合同测试可验证状态边界和 provider-free wiring | 无；没有逐动作授权 paired trace/semantic sidecar | **实现、可局部评测**；需幂等、掌握度/重测结果的成对语义证据 |
| `agent_version` identity | 两个 LearningLoop service 的显式声明；descriptor `runtime_capability_descriptor.py:73-112,252-265`；readiness `learning.py:426-438` | 真实 descriptor identity 测试、readiness release 测试；缺失值仍有 fail-closed 负向测试 | 无；版本声明存在但没有授权 trace/审批 | **实现、可核验但未授权**；下一步采集与 `learning-agent-v1` 绑定的 authorized evidence |
| `runtime_plan_version` identity | 学习服务 `plan_version`；descriptor builder `runtime_capability_descriptor.py:249-255`；readiness fallback `learning.py:426-428` | readiness API 与 release readiness 测试 | 无；当前只有代码/contract 版本，不是授权 trace | **实现、可评测**；必须与 suite、sidecar、checkpoint 和 release record 一致 |
| canary readiness | `learning.py:434-504`；`runtime_canary_release.py:86-149` | `test_learning_runtime_release_readiness.py`；evidence intake/preflight contract tests | 当前无 evidence，故不具备资格 | **可检查但未授权**；需要显式版本、结构 suite、semantic sidecar 和独立审批 |
| Legacy → Runtime 迁移/默认切换 | `learning_loop.py:91-190` 的分流和两个 Runtime adapter | 离线 collector、结构审计、semantic sidecar schema 可评测 | 未发现 LearningLoop 的真实授权 release record 或 canary decision | **未迁移完成**；保持当前 Legacy/受控 Runtime 路径，禁止默认提升 |

### 12.1 证据链顺序

对任一 LearningLoop capability，版本身份已由代码显式声明；后续必须按以下顺序补证据，不能把 readiness 当作授权：

1. 从 descriptor/readiness 核验 `agent_version=learning-agent-v1` 和对应 `runtime_plan_version`，并固定 release record 的 expected versions；
2. 在受控环境以同一输入采集 Legacy 与 Runtime 的真实成对 trace，保存脱敏 Task/学习结果、checkpoint 和事件摘要；
3. 通过 `collect_runtime_canary.py` 和 checkpoint/replay audit，生成同时绑定 Agent version 与 plan version 的 `authorized_paired` structural suite；
4. 由独立评审生成绑定同一 Agent/plan/suite/case 的 semantic sidecar；
5. 使用 `check_runtime_release_preflight.py` 显式传入 `--expected-agent-version` 与 `--expected-runtime-plan-version`；
6. 由有权限的发布者决定继续 Legacy、进入 canary、回滚或 default，并记录配置和回滚点。

本仓库当前已具备第 1 步的代码身份和离线门禁合同，以及第 3-5 步的工具/测试合同；仍没有 authorized 真实 trace、semantic sidecar 或独立发布审批。Mock、synthetic、readiness 和 preflight 的 provider-free 成功均不能填充“已授权”列。
