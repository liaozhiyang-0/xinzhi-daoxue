# 阶段 1.6 初始评估

评估日期：2026-07-17。评估基线为 `origin/main` 提交 `25a7a9b`，评估过程未修改原始教材 Markdown、PDF、图片或压缩包。

## 当前路由逻辑

- `POST /api/v1/tasks` 直接调用 `TaskCreationService.create_queued()`。
- `TaskCreationService` 默认将 `agent_id` 写成 `SOLVER_CT_V1`。
- `TaskRunner` 再次硬编码 `provider.run("SOLVER_CT_V1", ...)`，没有使用任务记录中的 Agent 路由结果。
- AE、DE 的解题任务因缺少显式路由，会错误落入电路理论 Agent；未知任务也没有 `unsupported` 状态。

## 当前知识库输入

- 配置输入为三个本地只读目录：`电路理论`（CT）、`模电`（AE）、`数电`（DE）。
- API 只读取 UTF-8 Markdown；不解析 PDF、不读取图片像素、不解压 ZIP。
- 本地资料不进入 Git 或 Docker 构建上下文，容器通过只读 bind mount 使用。

## 当前检索方法

- Markdown 按标题分节，再按固定字符数和重叠窗口分块。
- Unicode NFKC、英文大小写归一、连续中文和双字词项共同参与 BM25 风格评分。
- 仅内置“节点”到“结点”的替换、标题轻量加权和单字中文降权。
- 当前响应是 `list[KnowledgeHit]`，缺少标准化查询、置信度、警告、延迟和评分分量。
- 这是词项检索，不是 semantic、Embedding 或 vector 检索。

## 当前任务与知识库耦合点

- `TaskRunner` 从 `canonical_input.text/question/problem/query/prompt` 取第一个非空字符串。
- 检索调用发生在 Provider 之前；命中写入 `structured_result.knowledge`、结果 citations 和 Artifact `source_refs`。
- 仅产生粗粒度 `knowledge.retrieved` 事件；没有查询标准化、上下文构建和证据不足事件。
- 当前所有任务都会继续调用 Provider，不支持 LEARN_01 的纯本地 `retrieval_only` 分支。

## 当前测试覆盖

- 已覆盖非阻塞 HTTP 202、任务状态、递增 sequence、SSE 重连、取消、重试、Artifact、Mock Provider 和星辰未发布边界。
- 已覆盖三课程 Markdown 索引、课程过滤、`kb://` 路径安全和基础“节点/结点”归一。
- 尚未覆盖 Agent 注册与路由、AE/DE 解题拒绝、同义词、去重、多样性、阈值、检索上下文、证据质量、LEARN_01 和检索 benchmark 指标。

## 当前文档冲突

- 根 README 前半仍把 Vue3、Spring Boot、MySQL 写为当前技术路线，后半才描述 FastAPI、PostgreSQL、Redis、MinIO 的可运行基线。
- README 同时描述早期方案和阶段 0—1.5 实现，当前能力边界不唯一。
- `docs/architecture/02_xinzhi_multi_agent_platform_plan_v1.0.md` 仍是阶段摘要，并明确说明未收到用户所述完整总体架构原文。
- 本轮附件同样未包含该完整正文，因此不得虚构；现有架构文件应保留，待用户提供正文后原样补入。

## 阶段 1.6 修改范围

1. 配置驱动的 AgentRegistry、TaskRouter、路由事件与持久化字段。
2. 三课程知识库元数据、同义词和 OCR 清洗覆盖层，不修改原始资料。
3. 可复现的草稿评测集、baseline v1 与 local lexical v2 真实对比。
4. RetrievalContextPacket、证据质量和 LEARN_01 `retrieval_only` 最小闭环。
5. 统一任务入口、辅助评测 API、调试页、回归测试、OpenAPI 与阶段报告。
6. 不接入真实星辰 HTTP，不引入大型 Embedding、外部向量数据库或正式前端框架。
