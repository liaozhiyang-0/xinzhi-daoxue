# 工作台六业务场景运行矩阵（初始只读提取）

## 1. 范围与结论

本矩阵只记录当前 `apps/api/app/static/debug/workspace.html` 中实际展示的六个业务入口，以及它们在前端提交代码、场景注册、Agent 注册和 Runtime 装配中的预期链路。此阶段未修改业务代码，也未将静态推断当作真实运行结果。

六个入口中，前五个有前端场景 ID 映射；第六个“模拟电子技术 · 电路诊断与边界分析”没有 `showcaseScenarioByCapability.solve_problem` 映射，点击后 `scenario_id` 为空。另一个共同的前端 wiring 风险是：展示按钮的 `data-intent` 与 `data-course` 没有直接写入提交变量，当前提交路径使用 `intent="unknown"`、`course_id="AUTO"`（除非是学习跟进任务）。因此真实 E2E 必须以任务实际落库/事件中的意图、课程和 Agent 为准，不能只依据卡片文案判断路由正确。

## 2. 统一提交与运行链路

```text
工作台卡片 / 用户输入
  → 点击处理 data-capability、data-prompt、data-image-src
  → materialManager（可选上传 / 附件引用）
  → buildStudentTaskPayload()
  → POST /api/v1/tasks（只做轻量校验、任务/消息/事件持久化并返回 202）
  → _bind_auto_scenario / IntentRecognitionService（仅当 scenario_id 缺失时尝试补绑）
  → TaskRouter / AgentRegistry
  → AgentDefinition（enabled、course、intent、input_mode、timeout、retrieval_policy）
  → RuntimeExecutionBoundary / 对应业务 Runtime
  → ToolRegistry、RetrievalContextService、RAG、外部 Research Provider（按 Agent 定义）
  → RuntimeResultPipeline
  → AgentResultValidatorRegistry / ScenarioOutputContractService
  → TaskCompletionService（结果、Task/AgentRun/Node 状态、Session/Message/Event）
  → SSE /api/v1/tasks/{task_id}/stream，失败时前端 polling 对账
  → workspace.js renderResult / business view / evidence / KaTeX
```

前端当前统一 options 基线：

| 字段 | 当前来源或默认值 | 说明 |
|---|---|---|
| `request_id` | `student_${crypto.randomUUID()}` | 每次提交新生成 |
| `response_depth` | 深度选择框 | 由工作台控件决定 |
| `teaching_mode` | `direct_answer`；有学生作答时仍由 `inferLearningMode` 决定 | 不是场景路由字段 |
| `student_attempt` | 学生作答输入非空时附加 | 作业诊断卡片本身使用完整 prompt |
| `prefer_internal_agents` | `true` | 优先内部 Agent |
| `use_local_rag` | `true` | 是否使用本地 RAG 的偏好项，最终仍受 Agent 定义约束 |
| `source_task_id` / `learning_action` | 学习跟进场景才可能有值，否则空串 | 非卡片场景的跟进协议 |
| `research_analysis_v2` | 研究分析输入满足条件时附加 | 不等于 `RESEARCH_01` 已成功调用外部 Provider |

## 3. 六场景定义与运行预期

| scenario_id | 标题 | intent（卡片声明 / 当前实际提交） | course_id（卡片声明 / 当前实际提交） | options / 输入 | 附件要求 | 预期 Agent | 预期 workflow / Tool / Skill |
|---|---|---|---|---|---|---|---|
| `faculty_course_copilot_v1` | 教师智能备课 | `lesson_prep` / `unknown` | `CT` / `AUTO` | 标准 options；`teaching_mode=direct_answer`；无学生作答 | 不需要附件；仅文本 | `TEACH_01_LESSON_PREP_V1` | `LessonPrepRuntimeService` → `teach_lesson_prep` 多模态 RAG（本场景无图，按文本检索）→ 课程证据整理；预期技能 `CT.NODAL`、`CT.KCL`，并使用 `KNOWLEDGE.QUERY_REWRITE`、`KNOWLEDGE.GROUNDED_EXPLANATION` 的知识检索/依据约束 |
| `assessment_diagnosis_v1` | 作业批改与首错诊断 | `assignment_review` / `unknown` | `CT` / `AUTO` | 标准 options；无单独 `student_attempt` 要求，完整作业步骤在 prompt 内 | 不需要附件；仅文本 | `TEACH_02_ASSIGNMENT_REVIEW_V1` | `AssignmentReviewRuntimeService` → `teach_assignment_review` 文本 RAG → 首错、错误传播、分层提示、验证题；预期技能 `CT.NODAL`、`CT.KCL` 与常见符号错误依据，输出必须保留教师复核边界 |
| `student_learning_path_v1` | 学生个性化学习路径 | `learning_advice` / `unknown` | `CT` / `AUTO` | 标准 options；`use_local_rag=true`；完整成绩与错误证据在 prompt 内 | 不需要附件；仅文本 | `LEARN_01_LOCAL_RETRIEVAL_V1` | `KnowledgeQARuntimeService` → `local_retrieval` 文本 RAG → 学情证据与先修关系；预期技能 `KNOWLEDGE.QUERY_REWRITE`、`KNOWLEDGE.GROUNDED_EXPLANATION`，课程知识点预期涉及 `CT.KCL`、参考方向/符号约定；不得把一次错误变成能力定论 |
| `research_frontier_radar_v1` | 科研前沿检索与证据简报 | `academic_search` / `unknown` | `AUTO` / `AUTO` | 标准 options；研究 prompt 可能附加 `research_analysis_v2` | 不需要附件；仅文本 | `RESEARCH_01_ACADEMIC_SEARCH_V1` | `ResearchFrontierService` → `external_academic_search`；候选 Provider 包括 OpenAlex、Crossref、arXiv、SearXNG、阿里云 IQS、Bocha、Tavily、News RSS（按配置/可用性实际调用）→ 来源校验与证据表；预期技能 `RESEARCH.QUERY_PLANNING` → `RESEARCH.EVIDENCE_REVIEW` → `RESEARCH.EVIDENCE_SYNTHESIS`；外部 Provider 失败必须与系统失败区分 |
| `department_knowledge_governance_v1` | 学院知识库治理与课程资产发布 | `summarize_knowledge` / `unknown` | `CT` / `AUTO` | 标准 options；治理资产记录只在 prompt 内，不能补造字段 | 不需要附件；仅文本 | `LEARN_01_KNOWLEDGE_QA_V1` | `KnowledgeQARuntimeService` → `learn_knowledge_qa` / `governed_knowledge` 文本 RAG → 资产版本、来源、审批、权限和回滚清单；预期技能 `KNOWLEDGE.QUERY_REWRITE`、`KNOWLEDGE.GROUNDED_EXPLANATION`；治理结果缺资料时应保持未知/待复核 |
| （当前缺失） | 模拟电子技术 · 电路诊断与边界分析 | `solve_problem` / `unknown` | `AE` / `AUTO` | 标准 options；带单图片附件引用；`use_local_rag=true` | 必须附带示例图 `/debug-assets/question-bank/analog-opamp.jpg`，上传目的 `unified_task_material`；提交前形成 file attachment ref | `ACADEMIC_PROBLEM_SOLVER` | `AcademicSolverRuntimeService` → `academic_solver_domain_context` `method_only_rag`，文本 top-k 3、图片 top-k 2 → 图像读数/工作状态/边界分析；Agent 支持 `text_and_single_image` 与图片检索。当前没有对应 `scenario_id`/`config/scenarios.yaml` 场景契约，也没有明确 AE 专属 skill 条目，这是待验证的 `SCENARIO_CONFIG` 风险 |

说明：表中“当前实际提交”是静态追踪得到的提交默认值，不是 30 次 E2E 的替代。真实任务可能被后端意图识别器从 prompt 恢复，届时必须记录恢复后的 `intent`、`course_id`、`scenario_id` 和 `agent_id`。

## 4. 场景到后端注册的静态核对

| 场景 | `config/scenarios.yaml` | Agent Registry | 主要校验/展示契约 | 静态风险 |
|---|---|---|---|---|
| 备课 | 已启用；expected agent 与 Agent Registry 一致 | 已启用，45 秒，`local_runtime` | `lesson_prep` validator / renderer；输出目标、流程、练习、证据、复核边界 | 若前端 `unknown/AUTO` 未被识别，场景可能不能按预期路由 |
| 作业诊断 | 已启用；expected agent 与 Agent Registry 一致 | 已启用，45 秒，`local_runtime` | `assignment_review` validator / renderer；输出首错、正确步骤、分层提示、验证题 | 同上；缺标准答案时应为人工复核而非失败 |
| 学习路径 | 已启用；expected agent 为本地检索 Agent | 已启用，30 秒，`retrieval_only` | `learn_qa` validator / renderer；输出证据摘要、薄弱点、7 日路径、复测任务 | 场景配置允许 `explain_concept`，路由表也允许多个知识意图，需看实际 Agent |
| 科研简报 | 已启用；expected agent 与 Agent Registry 一致 | 已启用，30 秒，`local_model` | generic validator / renderer；结果依赖外部学术检索 | Provider 未配置/超时不应伪装为系统内部失败或生成无来源 DOI |
| 知识治理 | 已启用；expected agent 为课程知识问答 Agent | 已启用，300 秒，`local_model`；可按 Provider 失败降级本地检索 | `learn_qa` validator / renderer；治理 contract 对未知状态有特殊处理 | 后端只在识别到治理意图时自动绑定场景，前端若丢失意图可能无法进入治理 contract |
| 模电诊断 | 未发现对应场景条目；前端也未配置场景 ID | `ACADEMIC_PROBLEM_SOLVER` 已启用，120 秒，`local_graph`，支持图像 | generic validator / renderer；无对应 scenario output contract label | `scenario_id` 空、`course_id` 丢失、图片上传/图像 RAG/Agent 路由需真实 E2E 验证 |

## 5. 结果追踪字段与事件边界

后续每一次真实任务必须从当前 `/workspace` 新提交，并记录下列字段：

```text
scenario_id
session_id
task_id
intent
course_id
agent_id
provider
final_status
total_latency_ms
major_runtime_node
rag_or_tool_or_provider
failure_code
failure_message
last_task_event（event_type + sequence）
frontend_result_visible
```

统一失败分类仅允许使用：

`SCENARIO_CONFIG`、`ROUTER`、`AGENT_NOT_FOUND`、`AGENT_DISABLED`、`TOOL_UNAVAILABLE`、`RAG`、`EXTERNAL_PROVIDER`、`PROVIDER_TIMEOUT`、`RUNTIME_TIMEOUT`、`VALIDATION`、`PERSISTENCE`、`SSE`、`FRONTEND_RENDER`、`UNKNOWN`。

终态判定以 Task API / 持久化事件为准：`completed`、`failed`、`cancelled`；前端还必须检查是否存在可见回答/业务结果，避免把“任务已完成但页面无结果”误判为成功。SSE 通过 `/api/v1/tasks/{task_id}/stream` 接收事件，工作台在 SSE 出错或重连期间用任务轮询做终态对账。

## 6. 初始待证假设（不等同于故障结论）

1. 六个卡片的 `data-intent`、`data-course` 与提交 payload 之间可能存在 wiring 断点，造成 `unknown/AUTO` 路由。
2. 第六个卡片缺少场景 ID 和场景配置，可能导致 `SCENARIO_CONFIG`，即使 `ACADEMIC_PROBLEM_SOLVER` 本身已注册。
3. 前五个场景可能依赖后端 `IntentRecognitionService` 从完整 prompt 自动恢复；这不是稳定的场景契约，必须用任务记录和事件确认。
4. 科研场景的本地工作台结果依赖外部 Provider；Provider 无配置、超时、无结果和系统内部 Runtime 失败必须分开记录。
5. 六场景当前未发现静态的 Agent disabled/not found 结论；这只能通过后续 30 次真实任务确认。
