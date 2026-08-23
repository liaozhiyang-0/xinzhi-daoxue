# Agent Architecture Evolution Plan

## 1. 总体结论

当前系统已经有可持久化的 Runtime 控制循环，但智能能力仍被分散在 Supervisor、TaskRouter、Overall Router、固定计划编译器、业务 Runtime 和多个内部模型角色中。后续升级应以“一个 Planner、一个 canonical Plan、可检索 Skill、受限 Reflection、可治理 Experience Memory”为目标，不以增加 public Agent 数量为目标。

~~~mermaid
flowchart LR
    I[User Goal] --> P[PlannerService]
    P --> G[Goal + canonical Plan]
    G --> S[SkillRetriever]
    S --> T[Tool/Agent capability selection]
    T --> R[Runtime Kernel]
    R --> A[Generate / Tool / RAG]
    A --> C[Critic]
    C --> V[Verification]
    V --> M[Experience Memory]
    M --> E[Trace / Score / Failure Analysis]
    E --> P
~~~

目标不是让每个任务都产生自由形式的多 Agent 协作，而是让每次任务的目标、计划、技能、工具、批评、验证、经验都可以被审计，并且在预算、权限、证据和版本边界内运行。

## 2. Planner maturity：2/5

### 2.1 当前能力评估

| 能力 | 当前状态 | 评分判断 |
| --- | --- | --- |
| Goal 理解 | IntentRecognitionService、Supervisor 课程/意图识别、TaskRouter 结构化 intent context 已存在；但没有一个统一、版本化、面向用户目标的 Planner 输出 | 部分具备 |
| Task decomposition | IntentPlanCompiler 对 academic search 固定编译 3 个节点，其他多数场景是单 Agent 节点；Generic Goal 支持显式 required capabilities | 有模板，非通用动态分解 |
| 动态生成执行计划 | Runtime Controller 支持 bounded replan；Knowledge/Research/Generic Goal 存在受限 replan；计划主要由代码和请求 option 驱动 | 只在局部 Runtime 成熟 |
| Agent 选择 | TaskRouter deterministic scoring + OverallRoutingService 一次模型 refinement + fallback | 有选择，但多权威 |
| Tool 选择 | RouteDecision/IntentExecutionPlan 可携带 selected_tools；Runtime Handler Registry 能执行注册工具；没有统一 Planner 根据目标、风险和预算选择工具 | 执行可用，选择不统一 |

### 2.2 评分原因

综合为 **2/5**：

- 不是 0：已经有 Goal/Plan/Node/Capability 字段、候选路由、工具/子 Agent registry 和 Runtime replan；
- 不是 3：最终目标理解和分解依然分散在多个入口；大多数 plan 是固定模板或显式 option；Overall Router 与 deterministic Router 并存；
- 不是 4/5：没有统一的 plan quality gate、计划选择经验、跨任务 strategy reuse、Planner trace 和自动 failure-to-plan 改进闭环。

### 2.3 Planner 引入原则

新增的 PlannerService 不应直接替换 Runtime Kernel，也不应再复制一个“更大的 Router”。它应只拥有以下输出：

~~~text
PlannerOutput
  goal
  route_decision
  canonical_plan
  selected_skills
  selected_tools
  selected_agents
  context_requirements
  success_criteria
  budget
  explanation/lineage
  planner_version
~~~

Planner 只消费一次输入快照并生成一个可序列化 snapshot。Runtime 在新任务启动时消费 snapshot；恢复时只恢复 checkpointed snapshot；显式 replan 才能生成下一版本计划。

## 3. Skill System 缺口

### 3.1 当前已有能力

项目已经存在 apps/api/app/services/skill_registry.py 和 config/skills/CT.yaml、AE.yaml、DE.yaml：

- 有版本化 SkillDefinition、课程、章节、前置技能、problem type、capability id、错误特征和关键词；
- SkillRegistry.map_skills() 可按课程、problem type、capability 和 terms 做 bounded mapping；
- IntentExecutionPlan、RouteDecision 和教学 Foundation 已经能携带 selected skills；
- skill 目前主要是教学/课程元数据，不是通用 Agent 执行能力目录，也没有独立的 semantic retrieval 或 outcome memory。

因此，不应再创建第二个同名 SkillRegistry。

### 3.2 SkillRegistry / SkillRetriever / SkillMemory 判断

| 组件 | 当前是否存在 | 是否需要 | Phase C 处理 |
| --- | --- | --- | --- |
| SkillRegistry | 已存在，主要位于 service 层，课程覆盖有限 | 需要保留并抽象为稳定契约 | 让它成为唯一 Skill manifest；保留 YAML 兼容，增加能力描述、输入/输出、风险、版本和适用条件 |
| SkillRetriever | 没有独立组件；当前是规则 mapping | 需要新增 | 增加只读、可审计、可打分的 SkillRetriever；先复用现有 deterministic mapping，再逐步支持向量/语义检索，禁止直接让模型输出未注册 Skill ID |
| SkillMemory | 没有面向技能结果的经验记忆 | 需要，但不应直接复用用户 MemoryService | Phase E 作为 Experience Memory 的 skill-scoped projection，记录 skill 与 plan/tool/verification 结果，不保存未经治理的用户原文 |

### 3.3 建议目录与接口（仅规划）

本阶段不创建目录。后续可采用如下逻辑边界，数据与代码分离：

~~~text
skills/
  contracts.py          # SkillDefinition, SkillMatch, SkillExecution
  registry.py           # public SkillRegistry facade
  retriever.py          # SkillRetriever
  policies.py           # eligibility, risk, prerequisites
  adapters/
    legacy_config.py    # config/skills/*.yaml adapter
config/skills/          # 现有课程 skill YAML，保持兼容
~~~

建议接口：

~~~python
class SkillRegistry:
    def get(self, skill_id: str) -> SkillDefinition: ...
    def list_for_capability(self, capability_id: str) -> tuple[SkillDefinition, ...]: ...
    def validate_selection(self, skill_ids: list[str], context: SkillContext) -> SkillSelection: ...

class SkillRetriever:
    def retrieve(self, context: SkillContext, *, limit: int = 5) -> list[SkillMatch]: ...

class SkillExecutor:
    async def execute(self, skill: SkillDefinition, context: SkillExecutionContext) -> SkillResult: ...
~~~

Skill selection 的结果必须进入 canonical plan、事件和 trace；未注册、版本不匹配、前置条件不满足或风险超预算时 fail-closed。

## 4. Reflection 缺口

### 4.1 当前是否达到 Generate → Critic → Revision → Verification？

结论：**尚未达到通用闭环，当前约为 2/5。**

当前已有：

- Runtime Controller 的 observe → decide → act → verify；
- 部分 Runtime 在 verification 失败时支持 bounded replan；
- RuntimeResultPipeline、AgentResult validators、ScenarioOutputContract、SolverQualityGate 和 Academic Solver 的高风险 review；
- Knowledge/Research 场景对证据不足、引用和外部结果有专门验证。

但这还不是统一 Reflection：

- Verification 多数是 contract/schema/规则或业务 gate，不是一个统一 Critic Agent；
- 缺少标准化的 critic result：问题类型、证据、修正建议、置信度、是否需要重写；
- 缺少通用的 bounded revision 节点；
- 不同 Runtime 对失败的处理各自实现，无法按 trace 比较“首次回答为何失败、修改后是否真的改善”；
- 不能把某个场景的 replan 自动推广为所有任务的自适应策略。

### 4.2 Phase D 的 Critic Agent

新增 Critic Agent 的位置应在生成结果之后、最终验证之前：

~~~text
Generate / Tool / RAG
        ↓
Critic Agent（风险门控）
        ↓
0 或 1 次 bounded Revision
        ↓
Deterministic / Domain Verification
        ↓
Publish or Fail
~~~

Critic 输入：

- 原始 goal、success criteria、canonical plan；
- 草稿/结构化结果；
- RAG evidence、tool observations、引用；
- Runtime trace 摘要和已知风险；
- Agent/Skill/Tool/plan 版本。

Critic 输出建议：

~~~text
CriticResult
  status: pass | revise | fail | needs_review
  issue_types: factual | missing_evidence | reasoning | format | safety | scope
  evidence_refs
  required_changes
  confidence
  revision_budget_consumed
  critic_version
~~~

约束：

- 不对每个低风险任务无条件增加模型调用；由 capability policy、结果质量、证据状态和风险级别触发；
- Revision 默认最多 1 次，不能递归自我批评；
- 数值、单位、工具副作用和权限优先使用 deterministic/domain verification；
- Critic 不得创建未注册 Agent/Tool/Skill，也不能虚构 evidence；
- 未通过 Critic 或 Verification 的结果不能提交为 completed。

## 5. Memory 缺口

### 5.1 当前三类状态的边界

| 当前状态 | 当前用途 | 是否等于 Agent Experience Memory |
| --- | --- | --- |
| Session Memory | Session context、上一轮 agent/intent/topic/evidence、会话摘要和最近消息 | 否；是短期连续性 |
| Working State | Request options、Runtime checkpoint、plan、node state、observations、decisions、budget | 否；是可恢复执行状态 |
| Learning State | mastery score、wrong answer、retest、teaching interaction 和 feedback uptake | 否；是学习领域状态 |
| MemoryService / active memories | 用户显式记忆/偏好、冲突替换、忘记/恢复和上下文注入 | 否；是用户控制的长期偏好记忆 |
| Trace/ModelTracer/Evaluation | 任务执行、模型调用和评测证据 | 是经验来源，但当前没有被治理为可检索策略记忆 | 尚未完成 |

### 5.2 是否需要 Success/Failure/Strategy Memory？

建议需要，但必须把它们作为同一 Experience Memory 的三种受治理视图，而不是新增三个互不相干的数据库：

| 视图 | 存什么 | 不存什么 | 用途 |
| --- | --- | --- | --- |
| Success Memory | capability/skill/plan skeleton、输入特征摘要、工具与证据组合、验证结果、成本/延迟、版本、适用边界 | 原始学生隐私、未脱敏答案、未经评分的偶然成功 | Planner 提供候选策略 prior，不能直接当作答案 |
| Failure Memory | failure stage、error code、critic/verification issue、被拒原因、重试/修正结果、触发条件 | 把一次 Provider 波动写成永久事实；敏感原文 | Planner 和 Critic 避免重复失败，改进 fallback/plan |
| Strategy Memory | 抽象执行策略、前置条件、成功率/失败率、适用课程/skill、预算、版本 | 无约束的 prompt 拼接、未验证的模型自述 | 选择 plan/skill/tool 顺序，支持可回滚策略升级 |

经验记忆必须有：

- 脱敏和最小化；
- source trace/run id、Agent/Skill/plan version；
- confidence、evidence quality、evaluation provenance；
- TTL/淘汰、冲突和人工/自动 promotion；
- 按用户、课程、能力、Skill、风险隔离；
- 禁止把 Mock/synthetic 结果提升为真实成功经验；
- 读取经验不能绕过 Agent/Tool/RAG 的当前 eligibility 和 release gate。

## 6. Evaluation Loop 缺口

### 6.1 当前状态

当前并非只有“测试案例 → 人工分析”：项目已有 EvaluationCase、EvaluationRunner、EvaluationScorer、model trace、结构化失败阶段/错误类型、SuiteReport、runtime replay/canary audit 和多类 contract tests。这使当前评估成熟度约为 **3/5**。

缺口在于闭环后半段：

~~~text
Trace → Score
~~~

已经存在或部分存在；但：

~~~text
Failure Analysis → Improvement Proposal → Offline replay → Approval/Promotion
~~~

没有统一为每次失败都可消费的 Agent Experience/Planner 改进管道。现有评测结果主要是报告和门禁，不会自动、可追溯地生成新的 Skill/Strategy 或修改 Planner。

### 6.2 目标闭环

~~~mermaid
flowchart TD
    TR[Task/Runtime Trace] --> SC[Score route/plan/tool/evidence/result]
    SC --> FA[Failure Analysis stage + error + critic + cost]
    FA --> FP[Failure Pattern 脱敏聚合]
    FP --> IP[Improvement Proposal skill/strategy/policy]
    IP --> OFF[Offline Replay / Regression]
    OFF --> REV[Independent Review + Version]
    REV --> PROMOTE[Promote to Skill/Strategy Memory]
    PROMOTE --> NEXT[Planner candidate selection]
~~~

Promote 前的最低证据：

- 输入/输出/trace 有稳定 identity；
- Agent/Skill/plan/Tool 版本完整；
- 失败原因可重放或有明确不可重放标记；
- 至少一个离线回归集合改善且没有突破安全/证据门；
- Mock/synthetic/真实 Provider 证据等级分开；
- 需要改变默认路由或发布状态时，必须经过独立授权和回滚记录。

## 7. Phase A–E 路线图

### Phase A / Phase 1：架构收敛

目标：先减少控制面复杂度，不增加 public Agent。

规划动作：

- 冻结 SOLVER_CT v1.0、Task API、Chat API、AgentRequest/Result、Runtime Plan/Run、RAG、Tool、Event protocol；
- 把 TaskRouter 定义为 deterministic preflight/compatibility adapter；
- 将 Supervisor 限定为 /chat 协议适配和 trace 兼容；
- 将 OverallRoutingService 标记为 Planner 过渡实现；
- 统一记录 route revision、plan version、context snapshot、runtime launch identity；
- 建立“最终 owner”矩阵：Planner 负责目标/计划，Runtime 负责执行状态，Result Pipeline 负责发布资格，Session/Memory 只负责各自状态；
- 维持现有 Runtime release/readiness fail-closed，禁止用 synthetic/readiness 结果授权 default。

退出条件：

- 同一任务能从 trace 看出每一次 route/plan/context 变化的原因；
- /tasks 与 /chat 的最终执行入口能消费同一份 route/plan snapshot；
- 没有新增 Agent ID；
- 旧接口 contract tests 和 SSE 顺序/重连测试通过。

### Phase B / Phase 2：Planner 引入

新增规划组件：

~~~text
PlannerService
  ├─ GoalInterpreter
  ├─ CandidateBuilder
  ├─ Skill/Tool/Agent selector
  ├─ PlanCompiler
  └─ PlanPolicy / BudgetPolicy
~~~

替代旧逻辑：

- Supervisor._course/_intent 的智能判断；
- TaskRouter 中面向目标理解的复杂 keyword/scoring 分支；
- OverallRoutingService 的独立模型路由；
- 入口创建时与 Runtime 准备时的重复计划解释。

保留旧逻辑的位置：

- TaskRouter 只做输入/能力/版本/可用性/安全 preflight；
- FallbackRoutingService 只做 failure-safe availability fallback；
- RuntimeBusinessRegistry 只按 snapshot 解析已注册能力；
- Runtime 恢复只使用 checkpointed Plan，不重新调用 Planner。

迁移策略：

1. Planner shadow mode：只生成决策和 plan，不改变实际路径；
2. 对比 deterministic route、Overall route、Planner route 的 lineage；
3. 用 offline cases 验证 route/plan parity 和 fail-closed；
4. 按 capability canary 切换，保留 fallback 和 rollback；
5. 删除独立 Overall Router 前，至少完成一个版本周期的 trace 对账。

### Phase C / Phase 3：Skill Framework

目标：把“专业能力”从 public Agent ID 迁移为可注册、可检索、可复用的 Skill。

计划接口：

- SkillRegistry：沿用现有实现，扩展 descriptor/version/prerequisite/risk/IO；
- SkillRetriever：输入 goal、course、problem type、evidence state、learner state，输出 top-k registered skills；
- SkillPolicy：检查前置技能、课程/权限、工具依赖、风险和预算；
- SkillExecutor：通过 Runtime Handler/Tool/内部 worker 执行并写入 observation；
- SkillMemory：先作为 Experience Memory 的索引视图，不另建无治理的自由文本库。

目录规划：

~~~text
skills/                    # 逻辑能力层，Phase C 才创建
config/skills/*.yaml       # 当前课程配置继续兼容
~~~

迁移对象：

- Course/Intent classifier → Planner skill；
- Query rewriter → Knowledge/RAG skill；
- Circuit planner/vision extractor → Academic Solver skill；
- Research planner/reviewer/brief → Research skill；
- Teaching lesson/assignment strategies → Teaching skill。

退出条件：

- Planner 只选择 registry 中的 Skill；
- Skill selection 进入 plan/event/trace；
- 同一 Skill 可被至少两个合法入口复用而不复制路由；
- 新增课程 skill 不要求新增 public Agent；
- Skill 版本和失败结果能被 Evaluation Loop 识别。

### Phase D / Phase 4：Reflection

目标：在不破坏现有 deterministic verification 的前提下增加通用 Critic → bounded Revision。

新增：

- Critic Agent：统一结构化 critic contract；
- ReflectionPolicy：按 capability/risk/evidence/result state 触发；
- RevisionHandler：最多一次或配置的极小预算修订；
- CriticTrace：将 issue、evidence、required changes 与版本写入 Run observation。

迁移方式：

- 先在 Academic Solver、Knowledge QA、Research Evidence 三类高价值场景做 canary；
- 先运行 Critic shadow mode，不改结果；
- 再开启只允许一次 revision 的受控路径；
- 任何 critic/revision 失败都回到现有 fail-closed Result Pipeline；
- 不将“模型自我评价通过”视为业务验证通过。

退出条件：

- 可区分生成失败、Critic 发现、Revision 结果和最终 Verification；
- 失败结果不能提交为 completed；
- Critic 额外模型调用、延迟和成本可观测；
- 对低风险任务可证明不会无条件增加调用。

### Phase E / Phase 5：Experience Memory

目标：让成功/失败/策略经验服务于 Planner，但不污染用户 Memory、Learning State 或生产授权。

计划：

- 建立统一 ExperienceRecord contract，包含 scope、trace identity、version、evidence level、confidence、expiry；
- 生成 Success/Failure/Strategy 三种 projection；
- SkillMemory 通过 skill_id、course、problem type、risk 和验证结果检索；
- Planner 只能把经验作为候选 prior，不能绕过当前 registry/policy；
- 通过 Evaluation Loop 的 offline replay、独立 review 和版本 promotion 进入可用经验；
- 为用户隐私、删除请求和跨用户隔离提供明确策略；
- 先接入离线/受控 canary，再考虑影响默认路径。

退出条件：

- 经验可追溯到脱敏 trace 和评测结果；
- Mock/synthetic/真实证据等级明确区分；
- 失败经验不会被误当成成功策略；
- 经验读取、写入、promotion、forget/expiry 均有审计；
- Planner 使用 Experience Memory 的效果可在回放集上量化，而不是凭单次样例判断。

## 8. 各阶段共同的兼容与验证门

每个阶段都必须通过以下门禁后才能进入下一阶段：

1. git diff --check，配置/敏感文件检查；
2. Ruff、Mypy、Pytest 及针对性 contract tests；
3. Task 创建仍是非阻塞，路由不直接执行 Provider；
4. API/Agent/Runtime/RAG/Tool contracts 可反序列化并兼容旧 payload；
5. 事件 sequence、SSE cursor 和重连行为可验证；
6. Runtime resume 使用 checkpointed request/plan，不受当前配置漂移影响；
7. 真实 Provider、Mock、synthetic、offline evaluation 的证据等级分开记录；
8. 未执行 Docker、真实 Provider、授权 paired trace 或生产 canary 时，报告必须明确写未执行/未授权。

## 9. Phase 1 明确不做的事

- 不实现 PlannerService；
- 不修改 TaskRouter；
- 不创建 Skill 目录、SkillRetriever、SkillMemory 或 Critic Agent；
- 不改 Runtime Kernel、数据库、API、Agent 配置或 SOLVER_CT v1.0；
- 不把现有模型角色包装成更多 public Agent；
- 不把当前评测报告、Mock、synthetic contract 或 readiness 投影描述为真实生产能力。
