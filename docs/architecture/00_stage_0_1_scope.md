# 芯智导学多智能体平台阶段 0—1 架构摘要（保留快照）

> 本文完整保留阶段 1.6 开始前 `02_xinzhi_multi_agent_platform_plan_v1.0.md` 的阶段架构内容，作为阶段 0—1.5 的范围快照。原文件当时为 102 个物理行；需求中称其为“104 行阶段摘要”，仓库实际计数以 Git 基线为准。
>
> 当时已明确：附件未包含用户所述完整总体架构原文，因此没有虚构缺失章节。

## 1. 项目定位

“芯智导学”面向电子信息课程群，目标是形成可扩展的多智能体教学平台。本版本不建设完整多智能体编排，而是先冻结已经在讯飞星辰平台跑通的电路理论解题工作流，并用本地 FastAPI 建立稳定的业务协议、数据持久化与 Provider 隔离层。

## 2. 阶段边界

### 阶段 0：冻结现有基线

- 基线对象：`SOLVER_CT_电路理论专业解题_v1.0`。
- 保留现有星辰工作流，不改写其节点与提示词。
- 记录性能、能力、限制、回滚原则和待导出信息。
- 建立电路理论回归评测目录和指标清单。

### 阶段 1：本地 API 壳层

- 提供统一的 AgentRequest、AgentResult、AgentEvent、Artifact、CoursePack 协议。
- 通过 AgentProvider 屏蔽 Mock 与讯飞星辰的接口差异。
- 使用 FastAPI 提供会话、任务、事件、文件和产物 API。
- 使用 SQLAlchemy 2 与 Alembic 建立最小数据模型。
- 使用 SSE 提供任务事件流。
- 使用 PostgreSQL、Redis、MinIO 作为目标基础设施；测试环境允许 SQLite，本地开发允许文件存储回退。

## 3. 分层架构

```text
HTTP / SSE
    |
FastAPI routes
    |
Application services
    |---- repositories ---- SQLAlchemy / PostgreSQL or SQLite
    |---- provider factory ---- MockAgentProvider
    |                         \- XingchenCloudProvider
    \---- storage service ---- MinIO or local fallback
```

约束：

- 路由层不直接写 SQL。
- 业务层不感知星辰原始请求和响应字段。
- 未配置星辰时默认回退到明确标识的 Mock Provider。
- 配置全部来自环境变量。
- 日志不得输出密钥、数据库密码或完整学生隐私数据。

## 4. 核心数据流

```text
AgentRequest
  -> 创建 task
  -> task.created
  -> agent.started
  -> AgentProvider.run
  -> AgentResult
  -> 保存 task / agent_run / artifact
  -> task.completed
```

异常路径：

```text
ProviderError / timeout / configuration error
  -> 保存错误摘要
  -> task.failed
  -> API 返回统一错误或可查询的失败任务
```

## 5. Provider 接入原则

Mock Provider 是本地开发、CI 和无密钥演示的默认实现，返回结果必须包含 `provider=mock`。

Xingchen Provider 当前只建立隔离良好的适配器结构。以下信息尚未提供，不得推测：

- TODO：待补充正式 API Base URL。
- TODO：待补充鉴权 Header 或签名方式。
- TODO：待补充工作流执行请求字段。
- TODO：待补充同步响应与流式事件字段。
- TODO：待补充运行状态查询接口。
- TODO：待补充取消运行接口。
- TODO：待从讯飞星辰平台导出或人工补录工作流节点和提示词。

## 6. 当前不实现

- 完整 LangGraph 编排。
- RAGFlow 集成。
- Kubernetes。
- Celery 或分布式 Worker。
- 完整学生端、教师端、科研端。
- 十门课程的完整工作流。
- 自动执行用户上传文件。

## 7. 当时的后续演进

1. 补齐真实星辰协议并接入 `SOLVER_CT`。
2. 完成本地到星辰的端到端回归测试。
3. 建立最小调试页面，展示请求、事件与产物。
4. 在稳定协议上启动 `LEARN_01` 课程知识问答。

## 8. 阶段 1.5 补充边界

- 任务创建返回 HTTP 202，由进程内 TaskRunner 异步执行。
- 任务事件使用数据库递增 sequence，SSE 通过 Last-Event-ID 重连。
- 支持取消、失败任务重试、Artifact 持久化和本地调试页。
- 三课程本地 Markdown 以只读方式建立 BM25 风格中文词项索引。
- TaskRunner 是阶段性实现，API 进程重启可能中断运行中的任务。
