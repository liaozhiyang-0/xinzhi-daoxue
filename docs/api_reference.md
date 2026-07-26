# API Reference

新增接口：

- `POST /api/v1/chat`：创建非阻塞对话任务，返回 task/trace/result/stream URL。
- `POST /api/v1/chat/stream`：创建任务后推送原任务 SSE 事件。
- `GET /api/v1/chat/{task_id}`：读取统一 `AgentResponse`。
- `GET /api/v1/capabilities`：课程、意图、模态和本地/云能力。
- `GET /api/v1/workflows`：七个工作流的迁移与可用状态。
- `GET /api/v1/debug/traces/{trace_id}`：开发态 Supervisor Trace。

原接口继续兼容：`/sessions`、`/tasks`、`/tasks/{id}/stream`、`/files`、`/knowledge/*`、`/agents/*`。

```json
{
  "message": "为什么电容电压不能突变？",
  "user_id": "local-user",
  "course_hint": "CT",
  "debug": false
}
```

附件先通过原上传接口取得 `file_id`，再写入 `files`。服务端重新读取数据库元数据，不信任客户端伪造的 storage key、大小或校验和。
