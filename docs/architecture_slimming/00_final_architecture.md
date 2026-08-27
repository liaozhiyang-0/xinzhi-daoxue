# 当前正式架构

审计日期：2026-08-26/27

本文件是本轮收敛后的当前架构结论。逐文件职责见
`docs/repository_file_catalog.md`，详细运行时关系见 `03_runtime_graph.md`。

## 唯一活动链

```text
Student HTML Workspace
  → /api/v1/tasks（canonical）
  → UnifiedRequestPreparationService
  → AgentRegistry / ScenarioCatalog / TaskRouter
  → PlannerService（按配置生成 CanonicalPlan）
  → TaskCreationService.create_queued
  → TaskExecutor / TaskExecutionCoordinator
  → TaskRuntimeLifecycle / RuntimeTaskEngine
  → RuntimeExecutionBoundary / RuntimeBusinessRegistry
  → Agent capability + Skill/Tool/RAG/Model
  → Result governance + Result commit + Presentation
  → Task events / SSE
  → Student HTML Workspace
```

## 入口与边界

- `/student`、`/workspace` 和 `/workspace-legacy` 都服务同一个静态学生工作台；
- `/api/v1/tasks` 是任务创建、执行、事件、SSE 和结果的 canonical API；
- `/api/v1/chat` 只做会话、附件和输入适配，然后复用相同的任务创建与执行链；
- Provider 只能经由现有配置、Registry、Runtime 和环境变量进入，页面不直接调用 Provider；
- `ACADEMIC_PROBLEM_SOLVER` 是当前专业题求解入口，电路能力由 CT CoursePack、确定性 Tool 和结果治理承接；
- `RESEARCH_03_DATA_ANALYSIS_V1` 在默认冻结配置下不注入 Runtime 业务注册表，创建请求在 HTTP 边界失败关闭；
- 任务状态、事件顺序、Checkpoint、附件和会话由数据库/持久化服务承接，SSE 只投影事件。

## 已移除的平行架构

活动树中不再有 React Workspace、React Build Pipeline、React Runtime、独立 SOLVER_CT Runtime 或独立 Chat Runtime。历史材料保存在 `docs/history/`，不参与当前执行。
