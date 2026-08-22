# Phase E1：Memory / Trace / Evaluation 现状审计

## 结论

当前系统存在多种“状态”和“记忆”，但没有一个可直接替代它们的 Experience owner。Phase E 的 Experience Memory 必须作为独立、受治理的经验投影层，不能覆盖现有 MemoryService、Learning State、Runtime checkpoint 或 Session context。

| 对象 | 当前 owner / 用途 | 分类 | 可否产生 Experience candidate | 隐私与脱敏要求 |
| --- | --- | --- | --- | --- |
| `SessionModel.context_data` / `SessionContextService` | 当前会话连续性、前一任务摘要、课程与意图衔接 | USER MEMORY ONLY | 仅可作为当前任务输入特征，不直接写入经验 | 不保存完整原始聊天；只取课程、意图、摘要 ID 和长度等特征 |
| `SessionWorkingStateModel` | 会话工作态、版本化上下文 | EXECUTION STATE ONLY | 否 | 不能作为跨会话策略来源；原始内容按现有 owner 管理 |
| `LearnerKnowledgeStateModel`、学习交互与错题 | 学生掌握度、学习进度和教学反馈 | LEARNING STATE ONLY | 可由离线评测摘要间接引用，不直接升级为系统策略 | 学生标识、答案、附件和可回溯内容不得进入全局经验 |
| `MemoryService` / `MemoryModel` | 用户显式长期记忆、偏好、项目上下文 | USER MEMORY ONLY | 否，保持完全独立 | 沿用显式意图、用户隔离、敏感信息检测、删除语义 |
| `TaskModel` | 任务生命周期、输入/结果承载与业务状态 | EXECUTION STATE ONLY | 仅可在完成验证后作为 source ID | 只复制结构化特征，不复制完整输入或答案 |
| `AgentRunModel` | Agent Runtime run、plan/provider/version/status | EXECUTION STATE ONLY | 可提供 run provenance 和执行指标 | provider/model、trace、plan 版本可保留；原始 prompt/结果不可默认保留 |
| `AgentCheckpointModel` / `AgentRunNodeModel` | 可恢复运行的 append-only 快照和节点状态 | EXECUTION STATE ONLY | 否；仅作为 source reference | 不改变 checkpoint 恢复语义，不从 checkpoint 反推可复用答案 |
| `TraceStore` | 有 TTL 的摘要式节点轨迹 | AUDIT ONLY | 可产生 candidate source trace | 只使用 route/node/status/warning/error 摘要；不持久化 secrets/files |
| `ModelTracer` | 有界模型调用 metadata | AUDIT ONLY | 可提供模型/provider/version、耗时、token 等 provenance | 不保存 prompt、图片、reasoning 或原始学生内容 |
| `EvaluationCase` / `EvaluationRunner` / report | 可复现案例、评测结果、报告和 provenance | SOURCE OF EXPERIENCE | 是，优先从结构化评测与 replay 结果生成 candidate | 仅引用 case/eval ID、指标和摘要；不写答案、prompt 或完整 trace |
| Planner snapshot / lineage | Planner 版本、goal、plan shape、skill/tool 选择 | SOURCE OF EXPERIENCE | 是，可作为策略适用条件和 plan signature | goal 必须特征化；保留 capability/skill/tool/version，不保留原文 |
| Skill selection / Skill trace | 已注册 Skill 的选择、版本、policy 结果 | SOURCE OF EXPERIENCE | 是，限已注册 skill 和 policy 通过结果 | 只能引用 skill ID/version/binding；禁止经验引入未注册 skill |
| `ReflectionTrace` | Critic/revision/verification 的结构化审计 | SOURCE OF EXPERIENCE | 是，但 Critic pass 不等于 Success promotion | 仅保留 decision、reason code、metrics、evidence refs；不写 reasoning 原文 |
| post-processing summary | 任务完成后的会话摘要与连续性更新 | USER MEMORY ONLY | 否，除非被独立评测重新验证 | 不把摘要自动转成系统策略 |
| research ingestion / external evidence | 外部研究资料摄取和知识索引 | NOT ELIGIBLE FOR EXPERIENCE | 否；可作为当前任务 evidence | 资料 provenance 由知识 owner 管理，不能自动 promotion 为经验策略 |

## Candidate 来源与 evidence 门禁

允许 candidate 来源：successful verified run、failed run、Skill/Planner/Reflection evaluation、controlled canary observation 和 offline benchmark。所有 candidate 必须绑定 `source_trace_ids`、`source_run_ids` 或 `source_eval_ids`，经过摘要化和脱敏后进入候选态，不能直接 active。

`synthetic_provider_free` 只能用于结构验证和离线回放，不能静默升级为 production strategy；`offline_real_case` 可进入 validated，但仍需 promotion；`real_provider_test`、`controlled_canary` 和 `production` 必须保留真实 provenance。没有真实 Provider 证据时，Phase E 只能给 STRUCTURAL_GO 或 CONDITIONAL_GO，不能宣称答案质量提升。

## 隐私、promotion 与 owner 边界

- 默认禁止保存完整学生原始答案、联系方式/账号、未脱敏附件和不必要的原始聊天。
- 允许保存题型/错误类型、strategy skeleton、verification/critic code、版本、指标和 provenance。
- user-scoped 经验必须绑定 owner 并隔离检索；course/capability/global_deidentified 只能使用已脱敏、可评测记录。
- Success 必须有 verification pass、无 critical regression 且证据合法；Failure 可记录，但暂时性 Provider 故障不能泛化为永久策略；Strategy 需要多个支持样本或高质量评测、适用条件、反例/失败率、版本和可回滚/弃用信息。
- 不允许模型自写后直接 active，不允许 Critic pass 自动成为 Success，不允许自动修改 Prompt、Skill、Planner 或 Tool policy。

## 结论：MemoryService 是否独立

是。`MemoryService` 继续作为用户显式长期记忆 owner，保留现有 `MemoryModel` 语义、用户隔离、敏感信息处理和 forget 行为。Experience Memory 使用独立的统一 `ExperienceRecord` contract/storage；二者不共享 active 状态、不互相覆盖、不通过隐式复制形成事实源冲突。

## E1 状态

`PASS`。审计已完成，下一阶段建立统一 ExperienceRecord 与治理契约；本阶段未修改业务代码、数据库或 API。
