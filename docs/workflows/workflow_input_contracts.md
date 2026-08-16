# 工作流输入契约

## 两层契约

系统区分“业务字段”和“Runtime 输入合同”。材料提取器保留原文并生成业务字段；`AgentInputMapper` 再把这些字段映射到已登记的本地 handler。输入通过 `workflow_prompt` 文本封装传递业务字段，不把建议字段名冒充底层 Provider 参数。

`workflow_prompt` 包含原始问题、course_id、user_role、intent，以及按字段名排序的非空 `canonical_input`；不生成缺失值、不改数值、不包含二进制附件。

## 各 Agent 逻辑字段

| Agent | 必需 | 可选材料 | Runtime 输入 |
|---|---|---|---|
| LEARN | question, course_id, intent, request_id | retrieved_context, previous summaries, response_depth | 既有多字段契约 |
| SOLVER_CT | text | 单张 PNG/JPEG | 冻结 `AGENT_USER_INPUT`、`USER_INPUT_image` |
| TEACH_01 | workflow_prompt, course_id | topic, student_level, class_duration, lesson_count, goals, prerequisites, resources, constraints, response_depth | `AGENT_USER_INPUT`、`course_id`、`retrieved_context`、`request_id` |
| TEACH_02 | workflow_prompt | assignment_text, student_answer, reference_answer, rubric, maximum_score, teacher_requirements | `AGENT_USER_INPUT` |
| RESEARCH_02 | workflow_prompt | writing_task, document_type, audience, venue, source_text, trusted_sources, citation_context, style, language | `AGENT_USER_INPUT` |
| RESEARCH_03 | workflow_prompt | research_question, study_design, data_description, variables, sample_size, missing summary, provided_results, goal, constraints, environment, trusted context | `AGENT_USER_INPUT` |
| ROUTER_01 | workflow_prompt | role/course/intent/input hints, candidates, confidence, session context | `AGENT_USER_INPUT` |

Router 所需候选信息位于请求 options 中，并被确定性封装进 Router 文本输入。Router 只能在当前可用列表中选择。

## 材料提取

`RequestMaterialExtractor` 优先读取 JSON、显式标题、Markdown 标题和“字段：值”段落，支持教案、批改、写作和数据分析字段。失败时保留完整原文并给出 warning，不把指令误作学生答案，也不凭空补 rubric、结果或引用。

- 图片：仅 SOLVER_CT 接受一张 PNG/JPEG。
- TXT/MD/CSV/JSON：前端安全读取不超过 2 MB 的文本并附带元数据；CSV 只形成真实文本摘要，不宣称已执行统计。
- PDF：仅保存附件并提示粘贴关键文字；不宣称已全面解析。
- 本地附件路径不会作为底层 Provider 图片字段发送。

## 验证命令

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\validate_completed_workflows.py
.\.venv\Scripts\python.exe scripts\validate_completed_workflows.py --live --agent RESEARCH_03_DATA_ANALYSIS_V1
```
