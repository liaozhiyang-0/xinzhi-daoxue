# M3/M4：Backend Application、Capability、Runtime、Infrastructure、Governance 收敛

日期：2026-08-23

## 已完成的低风险迁移

### Application

- `TaskQueryService` 的唯一实现已移到 `app.application.tasks.query`。
- `TaskProgressReporter` 的唯一实现已移到 `app.application.tasks.progress`。
- API、bootstrap 和 task runtime preparation/execution 已改为从 application owner 导入。
- `app.services.task_query_service` 与 `app.services.task_progress` 只保留 deprecated re-export，供旧 importer 和测试兼容；没有复制实现。
- 既有 `TaskExecutionCoordinator`、`TaskLeaseManager` 继续作为 application task coordination owner。

### Infrastructure

- Runtime handler 的 provider/tool/internal-agent composition 已移到 `app.infrastructure.runtime_adapters`。
- `app.runtime.adapters` 只保留兼容 re-export。
- `app.main` 和 `GeneralQuestionRuntimeService` 直接从 infrastructure 导入 composition adapter。
- Runtime core `app.runtime` 不再在 package 初始化时导入 Provider/Tool adapter。

### Capability / Governance

现有 `app.capabilities.CapabilityRegistry`、`SkillRegistry`、reflection、experience、evaluation owner 保持不变；没有新增 public Agent、第二 Planner、第二 Runtime 或复制专业实现。高风险大型模块在 M1 matrix 中标为 partial/freeze，留待后续 owner-by-owner 迁移。

## 当前 owner 规则

```text
API → application use case → capability contract → infrastructure adapter
                                      └→ governance verification/reflection/experience/evaluation
application/runtime coordinator → single RuntimeTaskEngine
```

`RuntimeTaskEngine` 仍是唯一 Task 执行入口；Runtime 只持有 plan/lifecycle/checkpoint/recovery/policy/event semantics。KCL/KVL、RAG domain logic、教学设计、科研综合和学情诊断仍留在 capability/service owner，不下沉到 Runtime。

## 延后迁移

以下模块存在大量 importer、业务语义和既有 dirty worktree 重叠，Phase M 不做盲搬：`academic_solver_service.py`、`internal_agent_execution.py`、`learning_loop.py`、`rag_retrieval.py`、`research_local_analysis.py`、`course_asset_review.py`、`knowledge_audit.py`、`general_question_runtime.py`。它们由 M1 move matrix 管理，继续使用单实现和兼容路径，M7/M8 只在零 importer/回归证据成立时清理。
