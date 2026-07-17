# 本地总控层增量完善记录

## 当前主流程

- 正式任务入口为 `POST /api/v1/tasks`，请求合同为 `AgentRequest`，当前由 `TaskService.create_and_run()` 同步创建并执行任务。
- 会话沿用 `sessions` 表与 `/api/v1/sessions`；任务、事件、AgentRun 和 Artifact 均沿用现有表，不新增第二套持久化模型。
- 当前分支尚无 `TaskRouter`、Agent 注册表解析器和 RouteDecision；任务默认固定进入 `SOLVER_CT_V1`。
- 当前分支尚无知识库调用位置。其他现有工作分支已有三门课程的本地词项检索实现，本轮只在路由确定后调用，并限制课程、Top K 与字符预算。
- 当前分支的 `XingchenCloudProvider` 是协议占位实现；`feat/stage-2-xingchen-provider` 中已有真实鉴权、文字输入、单图上传和响应解析实现。本轮保护这些已经验证的字段，只扩展 Flow ID 与超时的 Agent 级选择。

## 文字和图片数据流

文字请求从 `canonical_input` 的 `text/question/problem/query/prompt` 中读取非空内容。图片先经现有 `/api/v1/files` 上传，再把单个附件引用放入任务请求；星辰实现继续使用已验证的文件上传接口及 `USER_INPUT_image` 参数。文字加图片保留原始文字，同时传递单张图片。多图、PDF、其他文件和空输入在 Provider 调用前拒绝。

## 本轮增量修改

- 在现有合同中补充输入模式、追问意图、路由结果和必要运行指标。
- 在 `agents/router.py` 与 `agents/registry.py` 中实现确定性快速路由、Flow ID/超时解析和云端调度白名单。
- 在现有 `TaskService` 中串联输入检查、最近会话上下文、路由、可选知识检索、云端调度、缓存、Provider 调用、结果归一化、Artifact 与事件。
- 扩展 `XingchenCloudProvider`，复用同一鉴权和 HTTP 客户端，根据 Agent 选择 Flow ID；不改动已验证的文字与单图请求字段。
- 增量更新 `agent_configs/registry.yaml`、`.env.example` 和现有 `/debug` 页面，并只补主流程关键测试。

## 明确不修改

- 不迁移课程资料，不调整用户当前对旧文档与课程目录的改动。
- 不替换数据库、任务入口、SSE、文件上传、MinIO 或 Redis。
- 不引入 LangGraph、RAGFlow、Celery、向量数据库、Embedding、新前端框架、长期记忆或多图/PDF 解析。
- 不重建星辰 HTTP 协议，不在日志、事件或 Artifact 中保存密钥、完整知识上下文或完整上游响应。

## 验证边界

本地使用 Mock/受控 Provider 验证路由、调度白名单、知识库失败降级、缓存命中、结果统一和追问上下文。真实联调只在本地 `.env` 已配置 Key、Secret 及对应 Flow ID 时执行；尚未发布或未配置的知识讲解与调度工作流记为 `BLOCKED_BY_CLOUD_FLOW`，不伪造成功。
