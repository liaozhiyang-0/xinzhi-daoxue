# Execution Surface Lockdown：冻结基线报告

日期：2026-08-25
分支：`refactor/platform-modernization`
工作区状态：dirty；已有用户前端、启动器、测试、审计文档和 `ci-artifacts/` 改动，未清理、未覆盖、未重置。

## 发布基线判定

当前公开稳定基线为：

```text
RELEASE_BASELINE_COMMIT = 5cb699c63bdccdfe454b12d40f399865954d2780
```

判定理由：该提交是用户指定的 GitHub 稳定基线，并有独立 H0 报告记录超时不重试保护和工作台文字、图片、通用问答、短追问四条浏览器 smoke 路径。其后提交暂不自动提升为发布基线：

| 提交 | 内容 | 当前证据 | 判定 |
|---|---|---|---|
| `f1180b6` | 冻结 H0 Harness/Circuit 基线 | 保护测试和 H0 报告 | 保留为基线证据，不改变发布基线 |
| `6b5a9c2` | 只读 Runtime Trace Projection | 83 项聚焦回归中的相关测试通过；已有附件提交浏览器证据 | 候选增强，待封印后重新验证 |
| `c0e68cf` | 视觉解析失败时保留显式文字题干 | Solver 回归通过；真实工作台问答输出完整答案，但当前 dirty 未跟踪前端出现 `renderInline is not a function` | 不自动认定为稳定发布基线 |

本报告不移动 `5cb699c`，不创建稳定标签，也不回退工作区。后续封印后的最终提交只有在专项测试和浏览器复测通过后，才可成为新的 `RELEASE_BASELINE`。

## 当前版本身份

| 身份 | 当前可核验值 | 结论 |
|---|---|---|
| `RELEASE_BASELINE_COMMIT` | `5cb699c63bdccdfe454b12d40f399865954d2780` | 已冻结，暂不移动 |
| `BUILD_ID` | 未在当前生产启动链中声明 | 风险；当前 dirty 工作台资源带有 `20260825-attachment-contract-v1` 查询参数，但它不是提交绑定的 build ID |
| `CONTROL_PLANE_VERSION` | `planner_mode=active`；`PlannerService.VERSION=planner-v1` | 已有明确 active Planner，但还需启动时封印校验 |
| `RUNTIME_GENERATION` | 未声明 | 本轮必须补充唯一代际身份；不能用文件存在性推断代际 |
| `CANONICAL_PLAN_VERSION` | `canonical-v1` | 已有合同版本；必须绑定当前 generation/build |
| `ACTIVE_RUNTIME_ENGINE` | `RuntimeTaskEngine` / `TaskExecutionCoordinator` 相关执行面 | 需要进一步证明唯一入口 |
| `TASK_EXECUTION_ENTRY` | `/api/v1/tasks` 及任务执行器恢复/重试路径 | 需要静态 import graph 和运行时 trace 双重确认 |

## 已执行的只读/验证检查

命令：

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline --decorate -20
.\.venv\Scripts\python.exe -m pytest --no-cov apps/api/tests/test_universal_academic_solver.py apps/api/tests/test_trace_projection.py apps/api/tests/test_observability_metrics.py apps/api/tests/test_orchestration_api.py apps/api/tests/test_showcase_case_matrix.py apps/api/tests/test_planner_controlled_takeover.py -q
```

结果：`83 passed, 2 warnings`。未执行全量 Pytest、Mypy、Docker、长时间 soak 或多轮浏览器矩阵。

服务重启后的静态可达性：

```text
GET /health    200
GET /workspace 200
```

当前本地工作台真实问答观察：

- 任务进入 `planner_active`，随后显示 Runtime 结果校验完成，状态为 `accepted_with_warnings`。
- 运算放大器知识问答正文完整展示，公式也进入页面 DOM。
- 页面同时出现 `renderInline is not a function` 前端告警；该告警来自当前未跟踪 dirty 工作台资源，不能把这次 dirty 运行当作干净发布证据。

## 冻结边界

本阶段开始时不做以下动作：

- 不修改 `SOLVER_CT v1.0`。
- 不删除或移动 Legacy 文件、历史任务、Checkpoint、Redis/DB 数据。
- 不修改已有 migration。
- 不启用旧 Router、旧 Runtime、旧 Handler 或旧 fallback。
- 不把 `c0e68cf` 或任何未完成浏览器验证的提交自动标记为发布基线。
- 不触碰现有未提交用户改动；`ci-artifacts/` 不进入本次提交，除非用户另行要求。

## 下一阶段门禁

只有完成以下检查后，才允许实施最小隔离改动并提升基线：

1. 盘点唯一 active Planner、Runtime、Task execution entry 和 completion path。
2. 生成 Production Execution Manifest，先作为 source of truth，不新增 Runtime。
3. 证明 Legacy executable object 不会被生产 bootstrap、Registry、Planner、Worker、Retry、Resume、Checkpoint 构造或调用。
4. 为 task/run/checkpoint/cache 补充或复用 generation/build/plan identity 围栏。
5. 对 dirty 前端 `renderInline` 告警单独处理，不将其与后端执行面封印混为一项。
6. 完成 stale task、重启恢复、冷启动和浏览器验证后，才创建最终锁定提交和稳定标签。
