# 自然语言自动调度架构

## 目标与边界

正式入口只有 `/workspace` 的一个自然语言输入框、附件、可选课程提示和更多设置。用户不需要选择知识问答、解题、备课、批改、写作或数据分析。Debug 页面可查看内部 Agent、映射和 Trace，但不是正式选择入口。

系统不会并行调用全部工作流。普通请求只选一个主工作流；仅显式的“先分析，再写作”可运行受控的 `RESEARCH_03 → RESEARCH_02` 顺序流水线。

## 调用链

```text
POST /api/v1/tasks
→ TaskRequestContext 与会话上下文
→ RequestMaterialExtractor
→ 本地候选评分与能力/可用性过滤
→ 置信度判断
→ 必要时 ROUTER_01_FALLBACK_V1
→ AgentExecutionPlan
→ Agent 专属 RAG/材料准备
→ AgentInputMapper
→ Local Runtime / ModelService
→ WorkflowOutputParserRegistry
→ AgentResultValidatorRegistry
→ 专属 fallback 或最多一次重路由
→ BusinessResultRendererRegistry
→ 统一 Presentation 与 SSE
```

任务创建只持久化请求并排队，Provider 调用仍在 `TaskRunner` 中异步执行。

## 本地路由

路由器综合课程、意图词、结构化材料、输入模式、角色、会话连续性、负向规则和运行时可用性。结构信号优先于普通关键词，例如 `student_answer + rubric` 优先批改，`source_text + writing_task` 优先写作。

- 高置信且分差充分：本地直接选择。
- 低置信、候选接近、短追问无上下文、课程冲突或多个强任务：进入本地确定性 fallback 或返回 `unresolved`。
- 本地 Router 不可用：返回 `unresolved`，不把模糊请求随意塞给 LEARN。
- Router 只能返回当前已启用、已发布、已配置并支持课程/输入模式的业务 Agent，不能返回自身。

候选分数、`reason_codes`、本地置信度、材料摘要和可用性检查进入任务 Trace；完整用户正文不会写入普通路由日志。

## RAG 隔离

| Agent | 模式 | 注入规则 |
|---|---|---|
| LEARN | `text_rag` / grounded generation | 课程证据进入生成并校验引用 |
| ACADEMIC_PROBLEM_SOLVER | CoursePack 方法参考 | 仅作为可核验方法证据，不冒充生成依据 |
| TEACH_01 | `multimodal_rag` | 课程概念、方法、例题进入教案上下文 |
| TEACH_02 | `text_rag` / reference only | 方法和常见错误可参考；评分以 rubric 为准 |
| RESEARCH_02 | `external_source_context` | 仅用户可信来源，课程 RAG 关闭 |
| RESEARCH_03 | `data_context_only` | 仅用户数据上下文，课程 RAG 关闭 |
| ROUTER_01 | `no_rag` | 不检索、不回答业务问题 |

`AgentExecutionPlan` 记录 `rag_mode`、策略名、是否使用 RAG、证据数、是否注入上下文和可用性检查。

## 重路由与循环保护

只有本地 Validator 确认能力不匹配且存在唯一可用目标时才重路由。当前自动规则是 `LEARN + CT完整求解 → ACADEMIC_PROBLEM_SOLVER`。`visited_agents` 防止回到已访问 Agent，`reroute_count` 最大为 1。

## 顺序流水线

明确要求“分析数据后写结果段”时先运行 `RESEARCH_03`。第一阶段通过验证后，平台把真实回答、`analysis_status` 和阶段 Trace 传给 `RESEARCH_02`。若第一阶段只有计划，第二阶段必须保留“未实际计算”的边界。其他复杂流水线返回 planned/insufficient。
