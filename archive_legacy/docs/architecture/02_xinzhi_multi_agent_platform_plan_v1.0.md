# 芯智导学多智能体平台架构（Stage 2.2）

## 1. 当前边界

平台保留一套 FastAPI 入口、一套 `TaskRouter`、一套 `TaskRunner`、一套 `AgentRegistry`、一套本地知识库服务和一套 `XingchenCloudProvider`。不引入第二套调度、Provider、结果合同或知识库，也不接入 LangGraph、RAGFlow、Celery、向量数据库、旧 Spring/Vue/MaaS 链路。

## 2. 注册模型

`agent_configs/registry.yaml` 是唯一工作流注册源。每个 `AgentDefinition` 包含：

- `agent_id`、`scene`、`provider`、`enabled`、`publication_status`、`mode`；
- `flow_env`、`course_ids`、`supports`、`fallback_agent_id`；
- `input_mapping` 和 `knowledge_top_k`。

Flow ID 只通过 `Settings` 的环境变量字段解析。状态接口只返回 `flow_configured` 布尔值，不返回 Flow ID、Key 或 Secret。计划态 Agent 允许 Flow 为空；已启用星辰 Agent 真正执行但配置不完整时返回 `agent_configuration_incomplete`。

## 3. 路由与降级

```text
AgentRequest
  -> TaskRouter 本地确定性匹配
  -> 已发布且可运行的目标 Agent
  -> 不可用时仅沿 registry fallback_agent_id 降级
  -> 未匹配时最多调用一次 ROUTER_01_FALLBACK_V1
  -> 校验 JSON、注册、启用、非自身、课程、输入和运行可用性
  -> 无有效目标则 unresolved
```

固定规则：

- CT `solve_problem` -> `SOLVER_CT_V1`。
- CT `check_user_solution` -> `CHECK_01_ANSWER_REVIEW_V1`；不可用时 -> `SOLVER_CT_V1`，并要求优先指出第一个错误。
- CT/AE/DE 学习类意图 -> `LEARN_01_KNOWLEDGE_QA_V1`；不可用时 -> `LEARN_01_LOCAL_RETRIEVAL_V1`。
- AE/DE 解题、UNKNOWN、未匹配或低置信输入不自动进入 CT Solver。

`route_confidence` 只衡量路由判断。`route_source` 使用 `local_fast`、`cloud_fallback`、`local_degraded` 或预留的 `session_context`。

## 4. 执行与 Provider

所有已注册的星辰 Agent 共用 `XingchenCloudProvider.run(agent_id, request)`：Provider 从注册表读取 Flow 环境变量名、文本参数名和图片参数名，再复用现有鉴权、上传、HTTP 请求、响应解析、错误映射和日志脱敏链路。禁止增加 Agent 专用 HTTP 方法。

支持的输入类型为 `text`、`single_image`、`text_and_single_image`。Solver 支持三类，其他当前注册工作流只支持文本；多图、PDF、空输入或不匹配的输入返回 `agent_input_not_supported`。

## 5. 知识库策略

- `SOLVER_CT_V1` 纯文本最多注入 Top 2 方法参考；带图片时跳过检索。
- 云端 `LEARN_01_KNOWLEDGE_QA_V1` 最多注入 Top 3 课程证据。
- `LEARN_01_LOCAL_RETRIEVAL_V1` 保持现有 `retrieval_only` 流程与 `kb://` 引用。
- routing_only Agent 不查询知识库。

## 6. 状态、事件与会话

现有 `AgentRun`、Artifact、SSE 和 Task 事件继续复用。路由场景、模式、课程、意图、来源、置信度、目标 Agent、降级信息、知识库命中和 Flow 配置状态写入现有 JSON 字段，因此 Stage 2.2 不需要数据库迁移。

`GET /api/v1/agents/status` 暴露非敏感注册与运行状态。`/debug` 显示同一组调度信息、Provider、状态、延迟和回答。会话上下文只保留后续 `session_context` 接入位，不实现长期记忆。

## 7. 扩展流程

新增工作流时只需：在注册表增加 Agent 定义、在 `.env.example` 增加 Flow 环境变量占位、发布后将状态改为 enabled/published，并添加对应路由与输入契约测试。无需复制 Provider、TaskRunner 或 HTTP 调用链。
