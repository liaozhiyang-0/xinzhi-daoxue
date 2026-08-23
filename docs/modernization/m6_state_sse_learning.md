# M6：Frontend State / SSE / Learning Migration

日期：2026-08-23

## State owner

React state 负责 sessions、active session、messages、current task、task events、loading/error 和连接状态。旧 Workspace 的 DOM class/dataset 不参与 React 主状态。

## SSE

`apps/web/src/hooks/useTaskStream.ts` 封装了既有任务流：

- 订阅 `/api/v1/tasks/{task_id}/stream`；
- 使用既有事件名和 `lastEventId` sequence；
- 浏览器 EventSource 保留服务端重连语义；
- effect cleanup 会移除 listeners 并关闭连接；
- completed/failed/cancelled 后刷新 Task projection。

没有修改后端 SSE 顺序、事件名称、持久化事件或重连协议。

## Task / attachments / learning

`api/tasks.ts` 统一暴露 submit、read、cancel、retry、pause、resume、runtime-controls；`api/attachments.ts` 保持既有上传接口；`api/learning.ts` 保持既有 `/api/v1/learning/actions` 边界，后续学习跟进通过 `StudentTaskPayload.options` 的既有字段传递。

本阶段不建立第二条 LearningLoop，也不把学习状态复制到浏览器。需要审批或断点恢复时，以服务端 projection 和 checkpoint 为准。

## Debug 与回滚

正式入口为 `/workspace`，旧实现保留为 `/workspace-legacy`；调试页面和既有 `/debug*` 路由继续由 FastAPI 管理。`/workspace-react` 作为显式 React 构建检查入口保留。
