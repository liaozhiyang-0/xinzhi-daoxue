# 架构迁移审计（历史记录）

> 本文记录 2026-07-21 迁移时的架构事实。外部星辰工作流及其 Provider 后续已废止并从活动代码移除；不要按本文的旧调用链配置或执行。当前运行事实以 `docs/repository_architecture_guide.md` 和代码为准。

审计时间：2026-07-21。审计对象为当前工作树；未移动或修改本地原始教材。

## 当前结构与技术栈

- 后端入口：`apps/api/app/main.py`，FastAPI + Pydantic v2。
- 任务入口：`POST /api/v1/tasks`，创建任务后由进程内 `TaskRunner` 异步执行。
- 前端入口：`apps/api/app/static/debug/` 下的原生 HTML/CSS/JavaScript，由 FastAPI 托管；仓库没有 `package.json`，不存在独立 Node 前端构建。
- 数据：SQLAlchemy 2 + Alembic；生产默认 PostgreSQL，测试使用 SQLite。Redis、MinIO、Qdrant 由 Compose 提供。
- 星辰：`XingchenCloudProvider` 使用已验证的 `Bearer key:secret`、`AGENT_USER_INPUT`、`USER_INPUT_image`、同步文字与单图片链路。
- 模型 API：`ModelRegistry` + `ModelService` 统一接入 Spark-X2 与百炼 Qwen 文本/多模态，集中处理超时、并发、一次重试、回退和脱敏 Trace；未配置 Key 不影响服务启动。
- 知识库：CT/AE/DE 原始目录只读；Markdown 经过标题感知切块，旧检索为 BM25/词项路径，新检索为 BGE dense + BM25 sparse + RRF + 可选 reranker，向量存储为 Qdrant。
- 向量化：当前真实文本模型为 `BAAI/bge-small-zh-v1.5`；新增确定性哈希 Provider 只用于旧索引兼容或开发态显式降级。
- 文件：元数据存数据库，正文保存到 MinIO；开发环境允许本地存储回退。

## 发现的问题

1. 对外任务契约偏底层，前端必须自行组装 `canonical_input`、场景和意图。
2. 路由、检索、Provider、回退、展示治理集中在较大的 `TaskRunner`，继续增加能力时耦合风险较高。
3. `mode` 同时承担内部运行分支含义，不能直接表达 local/xingchen/hybrid 迁移状态。
4. 星辰工作流与通用模型调用此前只有 `AgentProvider.run`，缺少 LLM、Workflow、Embedding、Vision 的显式边界。
5. 配置存在 `API_HOST` 与新架构所需 `APP_HOST`、旧兜底 Flow 名称等命名差异。
6. 本地知识问答降级此前只返回检索整理结果，没有直接星火生成层。
7. 多图/PDF 不能安全进入只支持单图的星辰链路；专业计算工具没有统一注册入口。
8. 调试 Trace 主要散落在任务事件和 RAG Trace 中，缺少 Supervisor 节点级摘要。

## 本次兼容改造

- 保留原 `AgentRequest`、`/tasks`、SSE、上传、数据库和星辰单图协议；新增 `AgentRequestV2` 并在 Supervisor 中转换。
- 新增 `/api/v1/chat`，但它仍创建原任务并交给同一 `TaskRunner`，没有第二套执行队列或任务路由。
- 新增 `execution_mode`、`local_handler`、`priority` 注册元数据；原内部 `mode` 继续兼容。
- 新增 LLM/Workflow/Embedding/Vision Provider 抽象；业务层不拼接平台 HTTP。
- 新增轻量 Graph Runner `XZD_SUPERVISOR`。当前依赖无需引入 LangGraph；节点边界可后续映射为 LangGraph 节点。
- 多图/PDF 在 Supervisor 中强制本地安全回退；多图逐张调用与 PDF 文本层提取已提供独立骨架。
- 真实 BGE 路径保持不变；哈希兼容层不会覆盖旧索引，迁移使用版本化集合与状态文件。

## 暂不修改

- `SOLVER_CT v1.0` 冻结基线、现有星辰字段与单图片上传链路。
- 原始教材、Markdown、图片、PDF 目录。
- 已提交 Alembic migration；本次不需要数据库结构变化。
- 现有静态前端的信息架构；本次只新增 API，不整体重做 UI。
- 七个云端工作流本体。

## 后续迁移

1. 将多图/PDF 预处理结果接入任务附件上下文，而不是仅安全回退。
2. 在人工验收星火回答质量后，把本地 RAG + 星火设为知识问答默认路径。
3. 扩展本地 Solver 的题目抽取和单位代数，保持星辰基线作对照与回退。
4. 将内存 Trace 迁移到持久化审计存储；不在 Trace 中保存文件正文或凭据。
