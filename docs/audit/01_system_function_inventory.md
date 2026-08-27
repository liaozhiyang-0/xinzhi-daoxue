# 芯智导学系统功能清单（只读审计初稿）

审计基线：`refactor/platform-modernization@3b017fb`
审计日期：2026-08-24
运行入口：`http://127.0.0.1:8000/workspace`

## 1. 现场与范围

本轮先完成仓库、运行服务、静态入口和 API 路由的只读扫描，没有修改业务代码，也没有读取或输出 `.env` 内容。

运行时 `/openapi.json` 共发现 **149 条路由**，其中包括 `/api/v1/*` API 与页面/调试入口。当前工作台不是 React/Vite 运行时：

- 页面入口：`apps/api/app/static/debug/workspace.html`
- 页面逻辑：`workspace.js`、`workspace-task-transport.js`、`workspace-materials.js`
- 通用渲染：`ui-core.js`
- 数学渲染：`vendor/katex/katex.min.js`
- React/Vite 页面源树已删除；Legacy 工作区直接使用静态 JavaScript 与三个保留的模块化传输/材料合同。

## 2. 运行时证据

| 项目 | 结果 | 证据/限制 |
|---|---|---|
| Git 基线 | 通过 | 分支 `refactor/platform-modernization`，HEAD `3b017fb`，工作区干净 |
| API 健康 | 通过 | `/api/v1/health` 返回 200；数据库、Redis、MinIO 均为 `ok` |
| 工作台页面 | 通过 | `/workspace` 和 `/student` 均返回 200 |
| Docker 基础设施 | 通过 | PostgreSQL、Redis、MinIO healthy；Qdrant 运行中 |
| Provider | 已运行 | `active_provider=local`，`provider_mode=local_runtime` |
| RAG | 部分通过 | 文本模型、图片模型、Qdrant 已连接；reranker 未加载 |
| 外部检索 | 已配置但未初始化 | arXiv、Crossref、OpenAlex 等显示 `deferred/not_initialized` |
| 健康延迟 | 需继续验证 | 10 次样本首个约 521ms，其余约 16–21ms；尚未完成任务运行期间压测 |
| API 进程内存 | 风险观察项 | 当前 Python 进程私有内存约 3422MB；尚未完成连续问答内存测试 |
| 管理统计 | 未验证 | `/api/v1/admin/task-summary` 未认证时返回 401，未使用凭据绕过 |

## 3. API 路由总览

以下数量由运行时 OpenAPI 扫描得到；详细参数和响应合同以 `/openapi.json` 及各 `apps/api/app/api/v1/*.py` 为准。

| 路由族 | 数量 | 主要能力 | 前端入口 | 后端实现 | 持久化/外部依赖 | 当前可用性 | 主要风险 |
|---|---:|---|---|---|---|---|---|
| `auth` | 6 | guest、登录、注册、刷新、登出、当前用户 | `login.html`、workspace guest | `auth.py`、`auth_service.py` | PostgreSQL、会话 Cookie/Token | 未做完整登录回归 | 未认证/guest 身份边界需验证 |
| `sessions` | 10 | 创建、列表、搜索、切换、归档、恢复、消息、摘要、任务历史 | `workspace.js` | `sessions.py`、`SessionService` | `sessions`、`conversation_messages`、上下文表 | 代码链路存在，待 E2E | user_id 与 localStorage 连续性需验证 |
| `chat`/`tasks` | 19 | 非阻塞创建、查询、重试、取消、暂停、恢复、审批、输入、结果、事件、SSE | `workspace.js`、`workspace-task-transport.js` | `orchestration.py`、`tasks.py` | `tasks`、`task_events`、`agent_runs`、结果/Artifact | 健康可用，核心任务未完整跑通 | 状态、重复提交、SSE/polling 竞态需测试 |
| `files` | 4 | 上传、元数据、分块、内容 | `workspace.js`、材料上传 | `files.py`、`DocumentIngestionService`、`StorageService` | PostgreSQL、MinIO、本地解析缓存 | 服务存在，图片链路待 E2E | 中文名、空文件、失败/超限需验证 |
| `memories` | 6 | 查询、创建、修改、软删除、恢复、忘记 | workspace 记忆设置 | `memories.py`、`MemoryService` | `memories`，可关联 session/message | 代码链路存在，待真实会话验证 | 自动记忆开关与上下文使用需验证 |
| `knowledge` | 22 | 资料、chunk、检索、RAG、图片/文档、发布/审核、OCR、reload、健康 | workspace 右侧资料；RAG 调试页；管理页 | `knowledge.py`、`KnowledgeBaseService`、`RAGRetrievalService` | PostgreSQL/本地资料、Qdrant、文本/图片模型 | `/knowledge/health` ready | 启动图片模型已加载；无结果、引用完整性待测 |
| `research` | 3 | 研究知识状态、检索、维护 | workspace academic_search | `research.py`、`ResearchKnowledgeService`、外部检索服务 | PostgreSQL、Qdrant、外部 provider/cache | 已配置但 provider deferred | 失败时不得生成假 DOI/来源，待真实失败测试 |
| `learning` | 11 | 学习状态、练习、指标、行动、Runtime 控制 | workspace 学习/教学模式 | `learning.py`、`LearningLoopService` | 学习/练习/复测表、Task Runtime | 未做核心用户链路验证 | waiting_user/review 与主输入状态需验证 |
| `agents`/`orchestration` | 6 | Agent 列表、定义、dry-run、capabilities、workflows | workspace 自动路由；agents 调试页 | `agents.py`、`orchestration.py`、`AgentRegistry`、`TaskRouter` | registry/config、Task 事件 | capabilities 可访问 | Agent ID、fallback、启用状态需矩阵验证 |
| `admin` | 18 | 管理概览、任务/文件/账号/审计/特性设置 | `admin.html` | `admin.py`、`AdminService` | PostgreSQL、审计日志 | 未认证返回 401 | 权限、敏感字段、管理写操作未测 |
| `auth/debug/evaluation` | 29 | 调试 Agent、RAG、执行链路、评测、报告 | debug 页面、脚本 | `debug_*.py`、`evaluation.py` | TraceStore、评测文件、RAG | 页面与路由存在 | debug 写操作边界与真实/Mock 标识需确认 |
| `models/observability/feedback` | 7 | 模型状态、指标、反馈 | 管理/调试页面 | 对应 API 与 Service | PostgreSQL、内存/TraceStore | 路由存在 | 真实任务指标与展示一致性待测 |

## 4. 数据与依赖地图

| 数据/组件 | 主要用途 | 当前证据 |
|---|---|---|
| PostgreSQL + SQLAlchemy | Session、Message、Task、Event、Memory、File、AgentRun、Artifact 等 | health `database=ok`；Alembic 版本存在 |
| Redis | Context cache；配置为 redis executor 时承载 Task ID 队列 | health `redis=ok`；当前任务执行模式为 local，队列指标为空 |
| MinIO | 上传文件和附件存储 | health `minio=ok` |
| Qdrant | 文本/图片/研究向量检索 | `/api/v1/knowledge/health` 显示 `vector_store_connected=true` |
| 本地知识库 | 课程资料、文档、图片和 chunk | RAG health 显示文本向量 27101、图片向量 3309 |
| Local Provider | 当前默认 Runtime Provider | health 显示 `local_runtime` |
| 外部学术检索 | arXiv、Crossref、OpenAlex、Tavily 等 | 已配置，但当前健康状态为 deferred/not_initialized |

## 5. 前端入口与展示能力

| 展示对象 | 代码位置 | 设计行为 | 当前审计结论 |
|---|---|---|---|
| 回答 Markdown | `workspace.js` → `renderMarkdown` | 处理回答、结构化结果和业务结果 | 代码存在，待浏览器实际渲染验证 |
| LaTeX/KaTeX | `workspace.html`、`ui-core.js` | 调用 `window.katex.render`，含安全结构检查 | 代码存在，复杂公式待专项测试 |
| 资料卡片 | `workspace.js` 的 `renderEvidence/evidenceCard` | 右侧 context evidence 展示本地资料、外部论文、图片 | 代码存在，截断/完整性待实际验证 |
| 会话历史 | `loadSessionList/loadSessionHistory` | 读取 messages 与 tasks，并用 request sequence 防旧请求覆盖 | 代码存在，快速切换/刷新待浏览器测试 |
| 图片材料 | `showMaterialPreview/uploadMaterials` | 本地预览后上传并写入 task attachments | 代码存在，真实 MinIO/Agent 输入待验证 |
| SSE/polling | `workspace-task-transport.js`、`workspace.js` | Task stream、事件游标、轮询终态 | 代码存在，断线/重复渲染待验证 |

## 6. 测试覆盖初步判断

仓库已有大量 API、Runtime、RAG、研究和合同测试文件，但本轮尚未运行完整测试，也没有把现有测试逐条映射到上述 149 条路由。因此本表不把“存在测试文件”当作“用户功能已验证”。下一阶段需要优先运行现有测试并补核心端到端 smoke。

## 7. 初步风险清单

1. **P1 候选：启动资源边界**。当前 `/api/v1/knowledge/health` 显示图片模型已加载，需验证纯文本问答是否仍调用或仅预热占用；目标要求普通文本不加载图片模型。
2. **P1 候选：任务 Runtime 超时**。需要以 100ms 测试超时验证 Task、AgentRun、Node 和 `task.failed` 事件是否全部收敛。
3. **P1 候选：任务创建边界**。`/api/v1/tasks` 在创建前会进行会话上下文组装，需用延迟注入确认 202 是否仍非阻塞。
4. **P1 候选：前端异步竞态**。代码已有 `requestSequence`/`historyRequestSequence`，但 SSE、polling、切会话、刷新和连续发送尚未做真实浏览器验证。
5. **P2 候选：资源占用**。API 私有内存约 3422MB，需完成连续 10 次文本问答及 3 并发测试后再决定是否启用现有 Redis Worker 隔离。
6. **P2 候选：外部检索失败边界**。当前 provider 尚未初始化，论文检索成功、超时、无结果和证据格式尚未验证。

## 8. 下一步

先补能准确失败的测试：图片检索条件、Runtime 超时、非阻塞任务创建、前端状态竞态；然后只修复已证实的最小问题。禁止在此基线阶段重新引入 React/Vite 或重写 Runtime。
