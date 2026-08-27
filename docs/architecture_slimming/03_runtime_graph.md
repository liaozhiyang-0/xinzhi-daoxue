# 当前运行时文件关联图

## 主链

```text
workspace.html / workspace.js
  → apps/api/app/api/v1/tasks.py
  → UnifiedRequestPreparationService
  → AgentRegistry + TaskRouter
  → PlannerService（active 时生成 CanonicalPlan）
  → TaskCreationService.create_queued
  → task_executor / TaskExecutionCoordinator
  → TaskRuntimeLifecycle
  → RuntimeExecutionBoundary
  → RuntimeBusinessRegistry
  → AcademicProblemSolverRuntime / KnowledgeQA / Teaching / Research
  → RuntimeResultPipeline + TaskResultCommit
  → TaskPresentation + conversation/learning state
  → task events / SSE / workspace.js
```

## 输入与配置关联

- `agent_configs/registry.yaml` 定义 Agent、handler、能力、输入输出和 fallback；`AgentRegistry` 解析它，
  `TaskRouter` 只选择可用目标。
- `config/scenarios.yaml` 只定义展示案例与场景约束；`ScenarioCatalog` 负责绑定和冻结场景过滤。
- `config/models.yaml`、`config/model_routes.yaml` 由 `ModelRegistry`/`ModelService` 使用，Provider 凭据
  只从环境变量进入，不由 Agent 或页面硬编码。
- `config/course_assets/`、`knowledge_config/`、本地课程索引和 `RAGRetrievalService` 共同形成课程证据链。

## 持久化与协议关联

- `apps/api/app/models/entities.py` 对应任务、事件、Runtime run、附件、会话、学习状态等表；
  `apps/api/alembic/versions/` 只允许新增 migration。
- `TaskEvent`/SSE 的顺序由事件服务、事件表和 `event_stream` 共同约束；断线重连使用 cursor/Last-Event-ID。
- `TaskResultCommitService` 负责结果落库，`TaskPresentationService` 负责向页面和 Chat 兼容响应投影。
- `docs/api/openapi.json` 是 API 导出快照；页面不承担 Provider、RAG 或任务执行逻辑。

## 特殊边界

- `/api/v1/chat` → `XZDSupervisor.prepare` → `UnifiedRequestPreparationService` → `TaskCreationService`，
  不创建第二个队列、Worker 或 Provider 客户端。
- `RESEARCH_03_DATA_ANALYSIS_V1` 在关闭配置下仍可被能力接口标记为 frozen，但没有进入 Runtime 业务服务
  注册表，任务 API 在创建前返回 409。
- `apps/api/app/static/debug/ts/` 的三个保留模块是 Legacy 工作区的实际模块依赖，不是可随意删除的前端残留。
