# Pilot 数据采集说明

## 采集范围

Pilot 只依赖正式产品产生的 `Account`、`Session`、`Message`、`Task`、`TaskEvent`、`AgentRun`、`Feedback` 和证据元数据。每批测试为任务输入的 `pilot_batch_id`，每个案例使用 `scenario_case_id`，单任务排查使用 `task_id`。

## 建议批次字段

| 字段 | 示例 | 说明 |
|---|---|---|
| `pilot_batch_id` | `phase-f-202608` | 一次测试批次的稳定 ID |
| `scenario_case_id` | `AC-01` | 六个示范案例或正式测试案例 ID |
| `course_id` | `CT` / `AE` | 课程维度 |
| `role` | `student` / `teacher` | 角色筛选由账号表提供 |
| `task_id` | UUID | 失败归因和人工复核的最小定位键 |

## 采集步骤

1. 创建批次记录并约定窗口、课程、案例和测试角色。
2. 通过 `/workspace` 完成任务，不绕过 Task API 直接调用 Provider。
3. 记录每个任务的 `task_id`，提交反馈时使用同一任务 ID。
4. 使用 Admin 产品分析按 `pilot_batch`、`scenario`、`course`、`role` 和时间过滤。
5. 对失败任务用 `task_id` 打开 `/debug/execution`，把 trace、反馈和复核结论关联到同一条证据链。

## 推荐冻结字段

`tasks_created`、`tasks_completed`、`completion_rate`、`failure_rate`、`feedback_coverage`、`resolved_rate`、`satisfaction_rate`、`evidence_coverage`、`citation_coverage`、`review_required_count`、`task_latency_p50/p95/p99`、`replan_rate`、`fallback_rate`。

## 禁止采集

不在 Pilot 表格或 Dashboard 中复制完整 Prompt、学生学号、联系方式、私有附件原文、访问令牌、模型密钥或未经脱敏的内部日志。比例指标必须连同窗口和分母定义一起导出；样本数为零时保留 `null`，不填 0% 作为结论。

