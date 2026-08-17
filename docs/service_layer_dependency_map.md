# 服务层依赖图与收敛候选（目标 4 阶段 1）

分析对象：`apps/api/app/services/`（154 个文件）中的三个服务系列：
`task_*`（18）、`runtime_*`（18）、`teaching_*`（5），共 39 个文件。
分析方法：逐文件读取 `from app.*` 导入，构建有向依赖图。

## 结论

1. **无循环依赖**：三个系列构成有向无环图（DAG），合并不会引入导入环
   （前提：不把叶子工具向上合并进消费者）。
2. **单一执行咽喉点成立**：`TaskRuntimeLifecycle`
   （`apps/api/app/services/runtime_task_engine.py`）是 `POST /api/v1/tasks`
   的唯一执行入口：
   - 唯一生产构造点：`apps/api/app/bootstrap/runtime_task_engine.py:332`
     （`build_runtime_task_engine`），`main.py:294` 调用；
     worker（`apps/worker/worker.py`）复用同一 `create_app`。
   - `engine.execute()` 唯一调用方：`TaskExecutionCoordinator`
     （`apps/api/app/application/tasks/coordinator.py:72`），仅经
     `TaskExecutor` 协议到达；路由只调 `app.state.task_executor.submit`。
   - 例外（非任务执行旁路）：`task_control_service.py:163` 自建
     `RuntimeRunLifecycleService(enabled=True)` 用于取消路径；教学互动
     （`teaching_interaction_runtime.py`、`learning_loop.py`）运行自己的
     `RuntimeController/PlanExecutor` DAG，属独立领域。

## 主要依赖链（最长 5 跳）

- 准备：engine → `task_runtime_preparation` → `task_failure_service` →
  `runtime_execution_boundary` → `runtime_launch_policy` → `runtime_canary_release`
- 执行：engine → `task_runtime_execution` → `runtime_result_pipeline` →
  `teaching_foundation` → `teaching_execution_planner`
- 提交：engine → `task_completion` → `task_terminal_boundary` →
  `task_result_commit` → `runtime_execution_boundary` → `runtime_run_lifecycle`
- 失败：`task_failure_service` → `runtime_execution_boundary` → `runtime_run_lifecycle`

## 转发层与重复职责

| 文件 | 问题 |
| --- | --- |
| `task_executor.py` | 纯委托门面（Local/Queue → coordinator/queue） |
| `runtime_task_components.py` | 纯 DI 记录（14 字段），仅 bootstrap+engine 使用 |
| `task_terminal_boundary.py` | 纯顺序协调器，唯一逻辑（守卫）已在 `task_result_commit.ensure_terminal_success` 重复 |
| `task_query_service.py` | 仓库薄包装 + NotFoundError |
| `task_control_service.cancel`（L141-188） | 内联重实现 `TaskFailureService.mark_cancelled`（L45-96） |
| `runtime_agent_readiness._release_reason`（L401-429） | 镜像 `runtime_launch_policy._release_gate_reason`（L309-350） |
| `task_runtime_preparation.py:282` | 调用 `RuntimeRunLifecycleService._build_legacy_plan` 私有方法 |
| `runtime_result_pipeline._teaching_degraded_result` | 重塑 teaching_loop 指标，职责与 `teaching_foundation` 重叠 |

## 收敛候选（约束：不改 POST /api/v1/tasks 契约、SSE 事件顺序、DB schema）

### 已实施（阶段 2）

- **合并 `runtime_task_components.py` → `runtime_task_engine.py`**：`RuntimeTaskComponents`
  作为同模块 dataclass 保留（仅 bootstrap 与 engine 引用），独立文件删除，零行为变化。
- **折叠 `TaskTerminalBoundary.commit` 进 `TaskCompletionService`**：转发协调层删除，
  提交协议（`ensure_terminal_success → presentation → 状态翻转 → session_commit →
  result_commit`）由 `TaskCompletionService._commit_terminal` 直接持有，顺序不变；
  bootstrap 直连三个叶子服务。单元测试改为调用该私有方法，集成测试
  （`test_event_sequence`、`test_sse_event_order`）验证 SSE 顺序不变。
- **结构约束测试 `test_service_layer_constraints.py`**：
  - 服务导入图无环（DAG）；
  - 仅 bootstrap 可导入任务引擎（防平行执行入口）；
  - `TaskRuntimeLifecycle` 仅由 bootstrap 构造；
  - `engine.execute` 仅 coordinator 可达（防绕过引擎的新执行链）；
  - coordinator 不导入任何业务服务（执行只经引擎协议进入）。

### 待实施

1. （可选）`task_control_service.cancel` 委托 `TaskFailureService.mark_cancelled`
   —— 需为 TaskControlService 引入 runtime_boundary 依赖，风险较高，暂缓。
2. （可选）合并 `task_presentation.py` → `task_result_presentation.py`（纯视图函数，
   收益有限）。
3. （可选）`services/task_executor.py` 下沉 `application/tasks/`（churn 大、风险中）。

**不要合并**：`task_creation_service`（路由面、非阻塞）与准备/执行服务；
`task_session_commit`/`task_result_commit`（幂等边界不同）；`runtime_control_policy`
（被 tasks.py 与 learning_loop.py 直接导入）；`runtime_safety`（4 个服务共享工具）。
