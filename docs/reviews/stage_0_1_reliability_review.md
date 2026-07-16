# 阶段 0—1.5 可靠性审查

## 审查结论

本地单进程开发模式通过；生产级任务可靠性仍属于后续 Worker 阶段。

## 已确认

- 单任务事件使用数据库 `sequence`，并有 `UNIQUE(task_id, sequence)`。
- SSE 使用 sequence 作为 `id:`，支持 `Last-Event-ID` 和 `after`，Header 优先。
- 心跳不写数据库，终态事件发送后关闭流。
- Provider 异常会写安全错误摘要和 `task.failed`。
- Mock 取消同时覆盖 queued 和 running。
- 重试创建新任务，保留 `parent_task_id`、attempt 和旧记录。
- 附件对象、数据库记录和任务关联保持一致。
- 增量 migration 支持 SQLite/PostgreSQL 目标模型，并提供 downgrade。
- Docker API 依赖 PostgreSQL、Redis 和 MinIO 健康后启动。

## 审查中发现并已修复

1. 高：事件按 UUID/时间排序，重连可能漏或重复。已改为递增 sequence。
2. 高：SSE 不支持断点续传。已增加 Header/query cursor。
3. 高：后台执行异常可能不落终态。TaskRunner 现在统一写 failed/cancelled。
4. 中：取消任务没有运行记录。running 取消现在写 cancelled agent run。
5. 中：附件数据库失败可能留下脏文件。已增加补偿删除。

## 保留风险

- 应用被强制终止时，尚未运行到异常处理的任务可能保持 queued/running；后续 Worker 应增加租约、心跳和启动恢复扫描。
- sequence 使用任务行锁适合当前单进程和 PostgreSQL；未来多 Worker 需要继续进行并发压力测试。
- SQLite 测试不能覆盖 PostgreSQL 的全部锁与隔离级别行为，Docker 验证必须保留。
