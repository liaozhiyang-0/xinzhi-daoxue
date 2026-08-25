# 芯智导学核心调用链（只读审计初稿）

审计基线：`refactor/platform-modernization@3b017fb`
审计日期：2026-08-24
验证边界：本稿先依据当前代码、运行时 OpenAPI、健康接口和静态入口建立调用链；Case A-F 的完整用户级执行结果将在后续 smoke/integration 阶段补齐。

## 1. 运行时总链路

```text
workspace.html
  → workspace.js / workspace-task-transport.js
  → POST /api/v1/tasks 或 POST /api/v1/chat
  → SessionContext / ContextAssembly / ScenarioCatalog
  → TaskRouter 或 XZDSupervisor.prepare
  → TaskCreationService.create_queued
  → Task / Message / Event 落库
  → LocalTaskExecutor（当前模式）或 QueueTaskExecutor（redis 模式）
  → TaskExecutionCoordinator
  → TaskLeaseManager.prepare/heartbeat/recover
  → TaskRuntimeLifecycle.execute
  → TaskRuntimePreparationService
  → RuntimeExecutionBoundary
  → Agent Runtime / Internal Agent / Provider / RAG / External Retrieval
  → RuntimeResultPipeline / Reflection / Validation
  → TaskCompletionService / TaskResultCommit / TaskSessionCommit
  → TaskResultPresentationService / MathFormattingService
  → Task result 与 TaskEvent 持久化
  → SSE / polling / session history
  → workspace.js renderAnswer/renderEvidence/renderContext
```

## 2. 入口与执行器

### 2.1 HTTP 入口

- `apps/api/app/main.py::create_app` 组装 Provider、AgentRegistry、TaskRouter、RAG、Research、Context、Runtime 和 TaskExecutor。
- `apps/api/app/api/http_app.py::configure_http_app` 挂载 `/api/v1`，并将 `/workspace`、`/student` 指向 `static/debug/workspace.html`。
- `apps/api/app/api/v1/router.py` 汇总 23 个 API router 模块。

### 2.2 两种任务执行模式

当前运行配置通过 health 表现为 local provider，且 task queue 为空，代码路径为：

```text
TaskCreationService
  → LocalTaskExecutor
  → TaskExecutionCoordinator
  → TaskRuntimeLifecycle
```

当 `task_executor_mode=redis` 时，代码改为：

```text
TaskCreationService
  → QueueTaskExecutor
  → RedisTaskQueue.publish(task_id)
  → apps/worker/worker.py
  → TaskWorker
  → LocalTaskExecutor/TaskExecutionCoordinator
```

本轮没有启用第二个真实 API 或 Worker 实例。

## 3. Task 状态与持久化边界

当前任务状态枚举为：

```text
created → queued → running
                    ├→ waiting_user
                    ├→ waiting_review
                    ├→ completed
                    ├→ failed
                    └→ cancelled
```

关键持久化对象：

| 对象 | 作用 | 关键关联 |
|---|---|---|
| `SessionModel` | 会话、归档、记忆开关 | `user_id`、messages、tasks |
| `ConversationMessageModel` | 用户/助手可见消息 | `session_id`、`source_task_id`、sequence |
| `TaskModel` | 非阻塞任务、状态、输入、结果、lease | `session_id`、`user_id`、`agent_id` |
| `TaskEventModel` | 路由、进度、检索、结果和终态事件 | `task_id`、唯一 sequence |
| `AgentRunModel/Node` | Runtime 与节点状态、checkpoint | `task_id`、run/node lineage |
| `MemoryModel` | 长期记忆及软删除/版本 | `user_id`、可关联 session/message |
| `FileModel/DocumentChunkModel` | 上传文件、解析结果、chunk | owner、task、MinIO storage key |
| `ArtifactModel` | 回答、报告、结构化结果等产物 | `task_id` |

`append_task_event` 使用数据库锁、sequence 候选和唯一约束重试；SSE 使用相同 sequence 作为 `id`，但这些并发/重连行为仍需专项测试证明。

## 4. Case A：纯文本问题

### 入口与参数

工作台 `submit()` 读取问题、会话、课程/意图、回答深度和选项，调用 `POST /api/v1/tasks`。请求包含 `session_id`、`user_id`、问题文本、`intent`、`course_id`、`options` 和空/非空 attachments。

### 状态变化

1. API 进行身份归属、场景绑定、会话上下文读取和轻量路由。
2. `TaskCreationService.create_queued` 编译 IntentPlan，写入 Task、用户消息、`task.created`、路由/意图/计划及 `task.queued`。
3. 当前 local executor 将 task ID 交给 `TaskExecutionCoordinator`。
4. `TaskRuntimePreparationService` 获得 lease，写 `running` 与 `agent.started`。
5. Runtime 执行后进入结果校验、提交和终态。

### 输出

Task 结果包含 answer、structured_result、citations、warnings、metrics 等；workspace 通过 `renderResult`、`renderEvidence`、`renderInfo` 和 `renderMarkdown` 显示。

### 错误出口

路由不支持、输入验证、Provider/Runtime 异常、取消和超时应分别落为失败/取消状态并写 `task.failed` 或 `task.cancelled`。当前是否所有超时都能收敛，尚未完成注入测试。

## 5. Case B：带图片问题

### 入口与参数

工作台先在浏览器生成图片预览；`uploadMaterials()` 通过 `/api/v1/files` 上传文件，拿到 `file_id`、文件名、类型、大小、storage key、校验和和 ingestion 状态，再把附件引用放入 Task 请求。

### 后端链路

`files.py` 负责上传、元数据和内容读取；`StorageService` 对接 MinIO；`DocumentIngestionService` 解析文档/图片并更新 `FileModel`/chunks。创建任务时 `TaskCreationService` 再校验附件元数据、任务归属和图片数量。

### Runtime 行为

附件可进入 AgentRequest 的 `attachments`。RAG 支持文本和图片 query modality，图片 embedding provider 与 image collection 由 `RAGRetrievalService` 使用。需要重点验证：纯文本不能因为 Agent/intent 自动触发图片 provider，有真实图片附件或显式 `include_images=true` 时才允许。

### 错误出口

文件不存在、解析中、解析失败、类型/大小超限、MinIO 不可用、图片模型失败都必须变成清晰的 HTTP 错误或任务失败状态；本轮尚未完成真实文件矩阵。

## 6. Case C：课程知识库问题

### 入口与检索

文本问题按 Agent/intent 进入知识问答 Runtime，调用 `KnowledgeQAService` 和 `RAGRetrievalService`。检索服务当前包含 query rewrite、稀疏检索、dense/Qdrant 检索、候选融合、可选 reranker、图片通道和上下文构造。

### 资料与引用

`RetrievalContextService` 评估证据充分性；结果携带 evidence/citations/related_images 等结构。workspace 右侧 `context-evidence` 使用 `renderEvidence` 展示本地知识材料，必要时通过 `/api/v1/knowledge/documents`、`document-pages`、`images` 读取内容。

### 当前运行证据

`/api/v1/knowledge/health` 显示 RAG ready、Qdrant connected、文本向量 27101、图片向量 3309，reranker 未加载。健康状态不能替代真实命中、无结果、错误引用和长资料卡片测试。

## 7. Case D：复杂数学题

### 入口与 Runtime

复杂数学/电路问题沿 TaskRouter → Agent Runtime → Provider/内部 Agent 路径执行，结果可同时包含普通答案、`math_content`、structured_result、步骤和证据。

### 展示

`workspace.js` 选择 `math_content.markdown` 或结果 answer，交给 `ui-core.js::renderMarkdown`；页面预加载 `vendor/katex/katex.min.js`，渲染器对公式结构做安全检查后调用 `window.katex.render`。

### 风险

需要专项覆盖 inline/display math、矩阵、列表、表格、中英文混排、连续公式以及错误 LaTeX。当前仅完成静态链路确认，没有浏览器截图或 DOM 渲染断言。

## 8. Case E：论文/科研检索

### 入口与执行

workspace 的 academic_search 场景提交 Task；对应 Agent/Runtime 通过 `ResearchFrontierService`、`ExternalRetrievalGateway`、`ResearchKnowledgeService` 和学术搜索 provider 获取论文/证据。

### 输出

结果应包含标题、作者、年份、来源、URL/DOI/arXiv 标识、摘要/证据角色和检索范围；workspace 使用 `externalPaperCard`、`renderExternalPapers` 显示外部证据。

### 当前边界

health 显示 arXiv、Crossref、OpenAlex、Tavily 等 provider configured but deferred/not_initialized。本轮还没有真实成功、空结果、超时、伪造 DOI 防护测试，因此该能力只能标记为“代码存在、运行状态未完整验证”。

## 9. Case F：多轮会话与记忆

### 前端

`ensureSession`、`loadSessionList`、`loadSessionHistory`、`loadMemories` 和 `localStorage` 保存当前会话/最近任务。历史恢复同时读取 messages 与 session tasks，并用 `historyRequestSequence` 与 `isCurrent()` 防止旧会话异步响应覆盖新会话。

### 后端

`/api/v1/sessions` 提供会话列表、搜索、归档/恢复、消息、摘要和任务历史；`ContextAssemblyService`、`SessionContextService`、`SessionCompactionService` 负责短期上下文/摘要；`/api/v1/memories` 与 `MemoryService` 负责长期记忆。

### 数据闭环

用户消息在任务创建时写入 conversation message；任务完成后助手消息、working state、summary 和可能的 memory 写入数据库。下一轮通过 session_id 重新读取并组装上下文。

### 风险

需要验证快速切换会话、刷新、连续发送、历史中带图片消息、记忆关闭/开启和旧任务终态不能覆盖当前会话。

## 10. SSE 与 polling

后端 `/api/v1/tasks/{task_id}/stream`：

1. 读取 `after` 或 `Last-Event-ID` 作为 cursor。
2. 按 TaskEvent sequence 递增输出 `id/event/data`。
3. 没有新事件时发送 heartbeat。
4. Task 进入 terminal status 后关闭流。

前端同时维护 Task wait、状态轮询和运行控制刷新；代码有取消句柄和 request sequence，但必须用中断、重连、终态重复和切会话场景验证。

## 11. 统一错误出口

| 层级 | 预期行为 |
|---|---|
| HTTP 校验 | `422` 使用统一 `validation_error` payload |
| 业务异常 | `AppError` 映射 code/message/details |
| 未处理异常 | 记录 request_id 并返回 `internal_error` |
| Task Runtime | `TaskFailureService` 写失败原因、failure category 和 `task.failed` |
| Provider/检索 | 结果中保留 fallback/warning，不能伪造引用 |
| 前端 | 终态解除 loading，错误保留可重试入口 |

## 12. 待验证矩阵

| Case | 静态链路 | 运行时健康 | 真实端到端 | 当前结论 |
|---|---|---|---|---|
| A 纯文本 | 已确认 | 已确认服务正常 | 未执行 | 待 smoke |
| B 图片 | 已确认 | MinIO 正常、RAG 图片 ready | 未执行 | 待文件矩阵 |
| C 知识库 | 已确认 | RAG/Qdrant ready | 未执行 | 待命中/无结果 |
| D 数学 | 已确认 | KaTeX 资源存在 | 未执行 | 待浏览器渲染 |
| E 学术检索 | 已确认 | provider deferred | 未执行 | 受外部检索状态限制 |
| F 多轮记忆 | 已确认 | DB/Redis 正常 | 未执行 | 待 session race smoke |
