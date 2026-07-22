# 本地编排架构

```text
Web / API client
  -> POST /api/v1/tasks (student Workspace) / POST /api/v1/chat
  -> XZD_SUPERVISOR
       normalize -> course -> intent -> safe route -> trace
  -> existing TaskCreationService / TaskRunner / SSE
       -> local RAG -> InternalAgentHub -> Spark-X2 / Qwen (when configured)
       -> professional tools
       -> legacy provider baseline/fallback (backend compatibility only)
  -> AgentResult / artifacts / citations
```

`XZD_SUPERVISOR` 是轻量状态图适配层。它只执行确定性、低成本的输入标准化与路由准备，不在路由函数内执行 Provider。每次请求生成 `request_id`、`trace_id` 与 `run_id`；任务仍使用已有 `task_id`。

节点 Trace 只保存字符数、模态、课程、意图、目标 Agent、状态与耗时摘要。原始文件内容、完整用户隐私和鉴权值不会写入 Trace。

多图和 PDF 不会进入星辰单图请求：Supervisor 将它们标记为需要本地预处理，并选择安全本地回退。单图继续使用原有星辰上传链路。

`/chat` 对 CT/AE/DE 学习类请求优先选择本地 RAG Agent；学生 Workspace 的 `/tasks` 继续使用同一 TaskRunner，并将已验证的备课、作业初审、学术写作和数据分析 Agent 适配到既有工作流。备课使用同一任务内构建的 RAG 上下文，作业初审保持 reference-only。历史 Provider 只保留在后端兼容和故障回退层，正式学生前端不显示其名称、Flow ID 或状态字段。
