# P40：任务失败与路由聚合可观测性

## 背景

任务表已经记录任务状态、失败分类、Provider、路由状态和取消请求，但原有 `GET /api/v1/admin/task-summary` 只返回状态数量。仅看“失败了多少”无法支持教师或运维人员定位失败来源，也无法判断取消请求是否集中发生在某个运行阶段。

## 实现

管理端任务摘要新增以下聚合字段：

- `failure_category_counts`：失败任务按 `failure_category` 的数量；未分类失败不伪造类别。
- `provider_counts`：按 Provider 的任务数量。
- `route_status_counts`：按路由状态的任务数量。
- `cancellation_requested_count`：设置过取消请求标记的任务数量。

统计仍然只读取本地数据库，保留原有状态统计和管理员权限边界；没有新增数据库字段、没有改变任务创建或执行链路。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_admin_management.py -q
.\.venv\Scripts\python.exe -m ruff check apps/api/app apps/api/tests scripts
.\.venv\Scripts\python.exe -m mypy apps/api/app
```

回归测试覆盖失败类别、Provider、fallback 路由和取消请求标记的聚合结果。当前不执行真实 Provider、OCR 或 Docker 调用。

## 边界与下一步

- 该摘要不返回错误原文之外的敏感输入，也不将失败数量描述为模型准确率或教学效果。
- 下一步可以在此基础上增加时间窗口和延迟分位数，但必须明确采样/完整统计边界，避免大表扫描造成管理端请求阻塞。
- 三个演示案例仍由用户自行设计，不纳入自动统计或自动改写。
