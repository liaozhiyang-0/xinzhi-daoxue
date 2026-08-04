# P41：任务延迟时间窗口与分位数统计

## 背景

P40 补齐了任务失败、Provider、路由和取消聚合，但管理端仍无法区分排队慢、执行慢和统计是否完整。任务记录已有 `created_at`、`started_at`、`completed_at`，结果中也保存了本地运行指标，因此本阶段在不增加数据库字段的前提下补齐延迟观察入口。

## 接口

新增管理员只读接口：

```text
GET /api/v1/admin/task-observability
```

参数：

- `window_start`、`window_end`：左闭右开时间窗口，默认最近 30 天。
- `row_limit`：最多读取 20,000 条任务，默认 2,000。

响应包含：

- 任务状态、失败类别、Provider、路由状态和取消请求聚合；
- 总耗时和排队耗时的测量数量、平均值、p50、p95；
- `truncated` 和 `data_quality_warnings`，明确窗口数据是否超过读取上限或时间字段缺失。

## 统计边界

- 总耗时优先使用 `started_at → completed_at`，缺失时回退到结果指标中的 `latency_ms/total_latency_ms`。
- 排队耗时优先使用 `created_at → started_at`，缺失时回退到结果指标中的 `queue_latency_ms`。
- 总耗时只统计终态任务；排队耗时可统计已开始但尚未终态的任务。
- 分位数是在应用层对有界窗口内的已读取样本计算；`truncated=true` 时不能把结果解释为全量历史指标。
- 延迟缺失会通过 `data_quality_warnings` 暴露，不用 0 伪造性能结果。

## 验证与风险

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_admin_management.py `
  apps/api/tests/test_feedback_api.py -q
```

测试覆盖终态/运行中任务、平均值、p50/p95、时间窗口错误和反馈接口对共享延迟解析逻辑的兼容性。

本阶段没有真实 Provider、OCR、Docker 或数据库迁移，也没有修改冻结的 `SOLVER_CT v1.0/SOLVER_CT_V1`。三个演示案例仍不纳入自动化。
