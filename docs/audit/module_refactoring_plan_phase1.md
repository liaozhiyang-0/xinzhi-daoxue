# 模块职责审计与 Phase 1 重构处理建议

## 1. 判断原则

本表按“当前是否需要存在”和“下一阶段是否继续扩展”分开判断：

- KEEP：保留为稳定边界；后续只做契约化和内部简化。
- MERGE：保留兼容入口，但把职责并入更单一的权威模块。
- FREEZE：当前实现和接口继续可用，不再增加新分支/新 Agent；等待后续迁移或长期替代。
- REMOVE：确认没有兼容调用后删除。本阶段不执行删除。

本阶段结论中没有把任何源代码直接标记为可立即删除；REMOVE 表示迁移目标，而不是本次操作。

## 2. 核心模块职责审计

| 模块 | 当前职责 | 是否必要 | 当前问题 | 建议 | 处理 |
| --- | --- | --- | --- | --- | --- |
| Supervisor / XZDSupervisor | /chat 协议入口的课程/意图/输入规范化、legacy AgentRequest 转换、路由、本地知识优先、多图/PDF 兜底、图状态与 Trace | 兼容入口必要；独立智能决策不必要 | 与 TaskRouter 重复识别/路由；XZDGraphState 与 Task/AgentRun 形成第二套编排状态 | 保留为 API adapter 与 trace compatibility；把课程/目标/分解/Agent 选择迁入统一 PlannerService，Supervisor 不再新增业务判断 | MERGE |
| TaskRouter | 基于 AgentRegistry 的确定性意图、课程、输入类型、能力、可用性、fallback 与候选路由；生成 RouteDecision | 必要，尤其是安全 preflight 和旧 API | 类中仍有大量业务关键词和 fallback 分支；创建阶段路由与 Runtime 阶段 refinement 不是同一权威 | 冻结 RouteDecision/路由规则作为兼容边界；只负责 deterministic preflight、候选集和 capability checks；智能分解交给 Planner | FREEZE |
| OverallRoutingService | 使用一次受限模型调用，从候选 Agent 中选择目标并回填 route | 过渡期必要 | 是第三个路由器；调用后会重组上下文、更新 Task，且与未来 Planner 目标重叠 | 作为 Planner 迁移前的临时 refinement；Planner 上线并覆盖候选选择后合并，保留 route lineage 读取能力 | MERGE |
| Runtime Planner（AgentExecutionPlanner、IntentPlanCompiler、RuntimeGoalPlanner） | 将路由/意图/Goal/capability 编译为 IntentExecutionPlan、AgentExecutionPlan 或 AgentRunPlan | 计划能力必要 | 同时存在多个计划方言；业务 Runtime 也能独立 build_plan()；计划创建阶段和 Runtime 启动阶段可能重复编译 | 收敛为一个 canonical Goal → Plan 编译层；旧计划用 adapter；业务 Runtime 只提供 capability descriptor、handler 和领域约束 | MERGE |
| TaskRuntimeEngine / TaskRuntimeLifecycle | 获取 lease、准备任务、启动/恢复 Run、执行 Runtime、结果提交、失败/取消/关闭 | 必要，是当前可靠执行主链 | Facade 仍暴露若干兼容属性并聚合多个 service；职责多但大多是生命周期边界，不应继续承载路由/业务判断 | 保留生命周期 façade；继续把 prepare/execute/commit/failure 拆成内部服务，但不再从 Engine 增加新的 Agent 业务分支 | KEEP |
| AgentRegistry | 读取 YAML Agent 定义、场景/能力/输入/输出/检索/fallback、发布/配置/执行资格、路由规则 | 必要 | 同时承担目录、资格判断、fallback 和旧路由规则；配置 ID 与实际 Runtime service ID 有别名关系 | 保留为唯一 public Agent/capability manifest；逐步将 routing rule 变成 capability policy，避免继续增加 Agent ID | KEEP |
| InternalAgentHub | 管理模型驱动的内部角色、结构化 schema、Provider/model route、JSON recovery、vision/text 调用 | 必要，但不应作为 public Agent registry | OVERALL_ROUTER、classifier、rewriter、reviewer、planner 等内部角色数量多；内部角色与业务 Agent 概念混用 | 保留为模型 worker/skill executor；不再把内部角色暴露为顶层 Agent；OVERALL_ROUTER 迁入 Planner，classifier/rewriter 迁入 Skill/Tool capability | FREEZE |
| Academic Solver（AcademicProblemSolverService / ACADEMIC_PROBLEM_SOLVER） | 多模态学术题求解、课程上下文、工具/RAG、专业校验、结果契约、视觉提取与高风险复核 | 必要，是核心业务能力 | 体量大且同时承担生成、视觉前处理、校验、格式化；拆成多个专业 Agent 会重复路由和共享上下文 | 保持单一核心能力边界；把视觉提取、计算、校验作为可审计 Skill/Tool 节点；保持 SOLVER_CT v1.0 冻结兼容 | KEEP |
| Teaching Runtime | Lesson Prep、Assignment Review、Teaching Foundation、Teaching Interaction/learning actions、学习反馈与提示 | 必要 | 部分服务继承 GeneralQuestionRuntimeService，容易把教学策略和通用问答混在一起；教学动作与 Task Runtime 还有独立控制面 | 保留领域 Runtime；共享通用执行/验证 adapter，教学策略下沉为 Skill/teaching policy；LearningLoop 继续独立发布门禁 | KEEP |
| Knowledge Runtime | 本地知识库检索、查询改写、检索上下文、证据质量、Knowledge QA、learning advice/retrieval-only | 必要 | LEARN_01_KNOWLEDGE_QA_V1 与 LEARN_01_LOCAL_RETRIEVAL_V1 有相邻语义；RAG/context 既被路由又被 Runtime/业务服务调用 | 保留检索与证据边界；把 QA 与 retrieval-only 作为同一 Learning Knowledge capability 的两个 output mode，短期保留旧 Agent ID | KEEP |
| Research Runtime | Academic Search、external retrieval/review/compose、Academic Writing、Data Analysis、Research Knowledge/Frontier | 必要 | 研究检索、写作、数据分析输出契约不同，但共享的外部证据/审查/来源治理流程分散 | 保留三个稳定业务 capability；合并共享 evidence/review/presentation pipeline，不合并成一个模糊 Research Agent | KEEP |

## 3. 其他关联模块的处理

| 模块/对象 | 处理 | 说明 |
| --- | --- | --- |
| DISPATCH_LOCAL_FAST_V1 | FREEZE | 它是路由基础设施，不应继续当作业务 Agent 扩展。 |
| ROUTER_01_FALLBACK_V1 | FREEZE → MERGE | 作为安全 fallback policy 保留；最终归入 Planner/Runtime launch policy，不再独立增长。 |
| GENERAL_QUESTION_V1 + GENERAL_MODEL_FALLBACK_V1 | MERGE（兼容别名） | 合并为一个 General Question capability 的 execution modes；保留旧 ID 解析、事件和结果兼容，避免同时维护两套近似生成路径。 |
| LEARN_01_KNOWLEDGE_QA_V1 + LEARN_01_LOCAL_RETRIEVAL_V1 | MERGE（内部实现） | 继续保留两个 public contract：QA 有回答/验证契约，retrieval-only 有证据/学习建议契约；实现层共享 Learning Knowledge runtime。 |
| SOLVER_CT_V1 | FREEZE | 遵守仓库冻结规则；不重写、不迁移其行为，不将 Phase 1 结论表述为基线改动。 |
| OVERALL_ROUTER_LOCAL_V1 | MERGE | 作为 Planner 早期模型选择器的兼容实现；Planner 上线后不再保留独立路由 API。 |
| COURSE_CLASSIFIER_LOCAL_V1、INTENT_CLASSIFIER_LOCAL_V1 | MERGE | 作为 Planner 的理解/分类 Skill，不作为 public Agent。 |
| QUERY_REWRITER_LOCAL_V1 | KEEP（Skill/Tool） | RAG 查询改写是能力节点，不需要 public Agent 身份。 |
| CIRCUIT_PLANNER_LOCAL_V1、CIRCUIT_VISION_EXTRACTOR_LOCAL_V1 | KEEP（Academic Solver Skill） | 继续作为 Solver 的专业计划/视觉技能；不拆成两个面向用户的 Agent。 |
| ACADEMIC_PAPER_REVIEW_LOCAL_V1、ACADEMIC_SEARCH_PLANNER_LOCAL_V1、RESEARCH_INTENT_CLASSIFIER_LOCAL_V1、RESEARCH_FRONTIER_BRIEF_LOCAL_V1 | KEEP（Research Skill） | 这些是研究 Runtime 内的受限 worker；保留 typed contract，但不提升为 public route。 |

## 4. 当前 Agent 数量是否过多？

结论：**存在概念上的过度分裂，但不是简单地按数量删除。** 当前配置至少有 13 个 agent_configs/registry.yaml 条目，InternalAgentHub 中约 15 个模型角色，Runtime 目录中又有多类业务 Runtime；其中包含路由基础设施、内部 worker、public capability、Legacy compatibility 和 Runtime adapter，不能把这些数字当成同一层的“Agent 数量”。

真正需要收敛的是职责层级：

1. **不应继续增加的 public Agent**：classifier、router、query rewriter、vision extractor、circuit planner 等都应是 Skill/Tool/worker，不应再占用 public Agent ID。
2. **优先合并的相邻能力**：General Question 与 General Model Fallback 统一为一个 capability 的模式；Knowledge QA 与 Local Retrieval 统一内部实现但暂时保留两个输出 contract。
3. **不应强行合并的能力**：Academic Solver、Teaching、Research 的结果语义、权限、证据和验证要求不同，合并成“万能 Agent”会把复杂度移到 prompt/条件分支中，长期更难维护。
4. **必须冻结的兼容项**：SOLVER_CT v1.0、旧 Agent ID、AgentRequest/AgentResult、现有 Task/Runtime 事件身份。

## 5. Runtime 是否过度复杂？

结论：**Kernel 复杂度是必要的，业务编排重复是过度复杂。**

### 应下沉或合并的能力

- 课程/意图/任务族/能力选择：下沉到 canonical Planner 的输入理解与 policy 层。
- route refinement 和 fallback target 选择：Planner 给出候选/目标；Fallback 只执行可用性降级，不重新理解目标。
- Context assembly 的调用策略：由 Planner/Runtime boundary 生成一次版本化 RoutingContext，执行阶段生成一次版本化 ExecutionContext；不要让每个路由器自行组装。
- IntentPlanCompiler、AgentExecutionPlanner、RuntimeGoalPlanner 的重复编译：统一到 canonical plan compiler，保留适配器。
- Academic Solver 中的视觉提取、计算、证据检索和质量校验：以 Skill/Tool 节点表达，但保持一个 Solver capability 的 public boundary。

### 应保留的能力

- Task 非阻塞创建、lease、bounded concurrency、recovery；
- AgentRun、状态机、Checkpoint、resume compatibility snapshot；
- Runtime Controller 的 observe/decide/act/verify 和有界 replan；
- Tool/Provider/Internal Agent typed handler registry、side-effect policy、approval/pause/input 控制；
- Result governance、terminal guard、Task/Session/AgentRun/Event 的一致性提交；
- Runtime release/canary/readiness 的 fail-closed 约束。

## 6. Supervisor 是否保留，还是升级为 Planner？

建议：**保留 Supervisor 名称和入口契约，但不再把它作为第二个智能控制器；新增 PlannerService 作为唯一智能控制权威。**

目标形态：

~~~text
/chat 适配层 ─┐
/tasks 适配层 ─┼─> PlannerService ─> Plan/Route snapshot ─> Runtime Kernel
Learning 入口 ─┘        │
                         ├─ deterministic preflight (TaskRouter)
                         ├─ Skill selection
                         └─ Tool/Agent capability selection
~~~

因此：

- Supervisor.prepare() 继续完成协议转换、Trace 兼容和必要的输入安全检查；
- 课程/意图/分解/Agent/Skill/Tool 选择迁入 Planner；
- TaskRouter 作为 preflight/compatibility adapter，不再与 Planner 争夺最终决定；
- Runtime 只消费已冻结的 plan snapshot，不在启动时重新解释用户目标，除非 explicit replan 合同触发。

## 7. Academic Solver 是否继续作为核心？

建议：**继续作为核心 capability，不拆成多个面向用户的专业 Agent。**

原因：

- 当前 solver 已经处理文本、图片、多图/PDF 本地预处理、RAG、工具计算、专业校验、输出契约和高风险复核；这些是一个“问题求解”能力的完整闭环。
- 拆成电路、模电、数电等多个 Agent 会复制课程判断、上下文组装、结果治理和 fallback；新增课程时维护成本更高。
- 课程差异应进入 SkillRegistry、course pack、solver policy 和可注册 handler；public route 继续使用 ACADEMIC_PROBLEM_SOLVER，SOLVER_CT v1.0 按冻结基线保留。

建议的长期边界：

~~~text
AcademicProblemSolver capability
  ├─ course/problem skill selection
  ├─ visual extraction skill
  ├─ deterministic calculator/tool
  ├─ RAG/evidence retrieval
  ├─ solver generation
  └─ verification/quality gate
~~~

## 8. 必须保持兼容的接口

Phase A 不改这些接口；任何后续迁移必须先增加 adapter 和 contract tests，再切换内部实现。

| 接口 | 当前位置 | 兼容要求 |
| --- | --- | --- |
| Task API | apps/api/app/api/v1/tasks.py | POST /tasks 继续 202 Accepted、创建非阻塞；Task 查询、事件、SSE、控制、重试、取消路径保持语义。 |
| Chat API | apps/api/app/api/v1/orchestration.py | /chat、/chat/stream、ChatSubmission、AgentResponse、trace/task/result URL 保持；Supervisor 可以变薄但不能让旧客户端改请求。 |
| AgentRequest | apps/api/app/contracts/agent.py | 保留字段、输入归一化、附件引用、options 兼容；新增 Planner 字段只能 additive，不能让旧 options 失效。 |
| RouteDecision | apps/api/app/contracts/routing.py | 保留 agent_id、intent、course_id、status、confidence、fallback、availability、route lineage；Plan snapshot 要能从旧 route 恢复。 |
| AgentResult | apps/api/app/contracts/agent.py | 保留 status、answer、structured_result、artifacts、citations、warnings、metrics、provider/mock 标记、fallback 和 trace identity。 |
| Runtime Plan | apps/api/app/runtime/contracts.py、contracts/intent.py | AgentRunPlan、RuntimeGoal、RuntimeNode、依赖/预算/版本/成功标准保持可反序列化；旧 IntentExecutionPlan 通过 adapter 接入 canonical plan。 |
| Runtime Run/Checkpoint | apps/api/app/runtime/contracts.py、repositories/migrations | run id、task id、state version、checkpoint sequence、launch/compatibility snapshot、pause/approval/recovery 语义保持；数据库只能增量 migration。 |
| RAG Interface | KnowledgeSearchRequest/Response、RAGRetrievalService、RetrievalContextService | 查询、证据 ID、score、index version、retrieval trace、insufficient/partial/sufficient 状态保持；Planner 不得绕过 evidence policy。 |
| Tool Interface | ToolRegistry、RuntimeHandlerRegistry、RuntimeHandlerDescriptor | handler ID、input schema、risk/approval/side-effect/timeout、observation/failure code 和预算边界保持；工具只能通过注册表调用。 |
| Agent Registry | agent_configs/registry.yaml + AgentRegistry | 旧 Agent ID、version、published/enabled、supports、fallback 和 SOLVER_CT v1.0 继续可解析；内部合并先用 alias，不直接删配置。 |
| Event protocol | AgentEventType、Task events、Runtime hooks/SSE | 事件顺序、cursor、重连、route reevaluation、plan/skill/tool/node/terminal 事件不能静默改变；协议变更必须增加顺序与重连测试。 |

## 9. Phase A 可执行范围（只规划，不实施）

### 保留

- Runtime Kernel、durable Run、Checkpoint/recovery、Task Coordinator；
- Agent Registry、Tool/Handler Registry、RAG/Provider adapter；
- Academic Solver、Teaching Runtime、Knowledge Runtime、Research Runtime 的 public capability 边界；
- 现有 Task/Chat/Runtime/Result/RAG/Tool contracts。

### 合并

- Supervisor 的智能判断 → PlannerService；
- Overall Router → PlannerService；
- IntentPlanCompiler + AgentExecutionPlanner + Goal compiler → canonical Planner/Plan adapter；
- General Question 与 General Model Fallback 的内部执行实现；
- Knowledge QA 与 Local Retrieval 的内部共享能力层；
- 内部 classifier/rewriter/planner/reviewer → Skill/Tool worker 层。

### 冻结

- TaskRouter 的 legacy route contract 和 deterministic preflight 行为；
- SOLVER_CT v1.0；
- public Agent ID、Task API、AgentRequest/Result、Runtime plan/run、RAG、Tool、Event contracts；
- 当前 Runtime release/readiness 的 fail-closed 语义。

### 删除候选（仅在后续证据确认无调用后）

- Planner 完成迁移后，独立 OverallRoutingService 实例；
- 仅用于旧路径、且已由 canonical plan adapter 覆盖的重复 plan compiler；
- 不再有调用者的 Supervisor 内部旧分支和重复 GraphState 字段；
- 合并完成且 alias 观测周期结束后的重复 fallback Agent ID。

## 10. 处理顺序建议

1. 先冻结当前 contracts、事件和 Agent registry 行为；
2. 建立 route/plan/context lineage 的对照 trace，确认每次改写的原因和最终 owner；
3. 引入 PlannerService 兼容 façade，不改变 Runtime Kernel；
4. 让 /chat 和 /tasks 都消费同一个 planner snapshot；
5. 迁移内部 model roles 为 Skill/Tool handler，再删除重复路由/计划边界。
