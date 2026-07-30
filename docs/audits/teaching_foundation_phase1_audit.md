# 教学闭环基础能力第一阶段实施前审计

## 1. 当前相关合同

- `AgentRequest` 通过 `canonical_input`、`attachments`、`context_refs` 和
  `options` 承载兼容输入，当前没有类型化 `TeachingMode`。
- `LearningActionRequest` 已有 `student_answer`，但没有可复用的
  `StudentAttempt` 分步合同。
- `SessionWorkingState` 已保存当前目标、课程、任务族、事实、纠正、假设、
  已完成步骤、待完成步骤和未解决事项，但没有明确的短期教学状态边界。
- `SolverResult`、`KnowledgeHit`、`RetrievalContextPacket` 和
  `EvaluationCase` 已是可扩展 Pydantic 合同，本阶段应增量扩展而非替换。

## 2. 当前 StudentAnswer 传递方式

- 学习动作通过 `POST /api/v1/learning/actions` 的 `student_answer` 传递答案。
- Workspace 的答案检查复用主输入框，未提供类型化学生过程输入区。
- `POST /api/v1/tasks` 的 `options` 已保存于 Task 输入 JSON，可兼容承载
  `teaching_mode` 和 `student_attempt`，无需第二套接口或数据库表。

## 3. 当前 SolverResult 字段

`SolverResult` 已包含题型、摘要、假设、已知条件、目标、方法、步骤、关键方程、
中间结果、最终答案、工具验证、知识点、常见错误、引用、置信度、执行路径、
验证报告、补丁和质量门结果。当前 `solution_steps` 是自由字典列表，主要包含
执行阶段信息，没有稳定 `step_id`，也不能默认解释为教学推导步骤。

## 4. 当前 KnowledgeHit 字段

`KnowledgeHit` 已包含 evidence/document/chunk 标识、课程、章节、section、标题、
内容、聚合分数、score components、source ref、文档 checksum 和相关图片。
页码与文档版本存在于 Chunk/Manifest，但未直接进入 Hit；缺失值必须保留为空，
不能推断或虚构。

## 5. 当前 WorkingState 结构

`SessionWorkingState` 是会话级短期工作状态，由
`SessionWorkingStateService` 维护并参与上下文装配。长期偏好由 `Memory`
维护，知识掌握状态由 `LearnerKnowledgeState` 独立维护。本阶段应在
WorkingState 中增加可选 `TeachingStateV1`，不得复制 StudentAttempt 到
Memory，也不得因提交 Attempt 自动更新掌握度。

## 6. 当前课程知识点来源

Solver 的 `knowledge_points` 目前是自由文本，通用 Solver 在部分路径中仅使用
`problem_type`。CoursePack 和 CapabilityPack 已提供课程与能力边界，但没有
稳定的 CT/AE/DE `skill_id` 和先修关系。因此本阶段采用小规模、版本化 YAML，
不建设知识图数据库。

## 7. 当前配置加载方式

课程包、模型注册表、知识库和学习掌握度配置均使用仓库根目录下的 YAML，并以
Pydantic/显式校验或加载器验证。本阶段的 SkillRegistry 和 ErrorPoolRegistry
沿用同一模式：启动时或服务构造时加载、失败即给出明确配置错误。

## 8. 当前评测案例加载方式

`EvaluationCaseLoader` 递归加载 `evaluation/cases` 下的 YAML/JSON 案例，
使用统一 `EvaluationCase` 合同验证，再由原 `EvaluationRunner`、scorer 和
report writer 执行。新增教学维度必须扩展原合同，不创建第二套 runner。

## 9. 本轮复用模块

- 原 `POST /api/v1/tasks`、TaskCreationService、TaskExecutor 和 TaskRunner。
- 原 Session、Task、ConversationMessage、SessionWorkingState 和历史恢复。
- 原 `ACADEMIC_PROBLEM_SOLVER`、`SolverResult`、Quality Gate 和 Presentation。
- 原 RAG 检索结果、RetrievalContextPacket、CitationValidator 和 Evidence View。
- 原 EvaluationCase、Rubric、Runner、Scorer 和 Report。
- 原 Workspace 静态前端、SSE、轮询回退和 Session 历史。

## 10. 重复实现检查

未发现现有稳定 `TeachingMode`、`StudentAttempt`、SkillRegistry、
SolutionPacketV1、EvidencePacketV1 或确定性错因池注册表。本阶段可以新增这些
小型合同、注册表与适配器。现有 StudentAnswerReview、Solver Quality Gate、
Memory、LearnerKnowledgeState 和 Agent Runtime 职责明确，不应复制或重建。
