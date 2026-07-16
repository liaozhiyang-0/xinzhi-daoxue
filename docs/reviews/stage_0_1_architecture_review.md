# 阶段 0—1.5 架构审查

## 审查结论

通过，适合进入自动化验证和用户审查。

## 已确认

- 路由只负责协议转换、依赖获取和 TaskRunner 提交，不直接执行 Provider。
- `TaskCreationService`、`TaskQueryService`、`TaskControlService` 和 `TaskRunner` 职责分离。
- TaskRunner 每次状态变更使用独立数据库 Session，Provider 等待期间不占用数据库连接。
- `AgentProvider.provider_name` 是显式字段，不再通过类名字符串推断。
- `XingchenCloudProvider` 只保留边界并抛出 `NotPublishedError`，没有真实传输代码。
- 进程内 Runner 的 `submit(task_id)` 接口可由后续 Worker 替换。
- 统一协议包含 `AttachmentRef`、`RunMetrics` 和 `ProviderAvailability`。

## 审查中发现并已修复

1. 高：任务路由同步等待 Provider。已改为创建 `created/queued` 后返回 HTTP 202。
2. 高：请求数据库 Session 被长时间任务占用。已改为后台独立 Session。
3. 高：Provider 名称通过类名推断。已改为显式 `provider_name`。
4. 高：星辰适配器保留可能执行 HTTP 的代码。已移除传输实现。
5. 中：任务服务职责过大。已拆分创建、查询、控制、运行和事件服务。

## 保留风险

- API 进程重启可能中断进程内任务；这是本阶段已记录限制，后续应迁移到独立 Worker。
- 当前没有实现多进程任务抢占和分布式锁，不应横向扩展 API 副本来共同消费任务。
- 完整总体架构原文未随本轮附件提供，当前只能保持已有架构基线。
