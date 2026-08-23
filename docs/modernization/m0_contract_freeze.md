# M0：Repository / Contract Freeze

日期：2026-08-23
分支：`refactor/platform-modernization`
基线 SHA：`3b017fb14c6aebcfd0b5a22d2879e532661059b6`

## 范围与工作树

Phase M 从 T5 完成提交建立独立分支。迁移前工作树已有用户未提交修改：147 个 tracked modified、42 个 untracked entry；这些修改不属于 M0，后续只暂存 Phase M 文件。M0/M1 不提交、不重置、不清理这些文件。

## 公共 API / OpenAPI

- OpenAPI 文件：`docs/api/openapi.json`
- path 数量：144
- OpenAPI SHA-256：`5c0a72bbe7097ce2b0f844398458920b571d705248a829daa7d6b20705b06de5`
- 当前 generated TS types：`apps/web/src/api-types.ts`
- generated types SHA-256：`53cb60883a674420e894f1e118d0d10e9e28d0647c7b95a0c9c5540fe8a33b8a`

必须保持的公共入口已确认存在：

| 领域 | 入口 |
| --- | --- |
| Task | `POST /api/v1/tasks`、`GET /api/v1/tasks/{task_id}`、`GET /api/v1/tasks/{task_id}/stream` |
| Chat | `POST /api/v1/chat`、`POST /api/v1/chat/stream`、`GET /api/v1/chat/{task_id}` |
| Session | `/api/v1/sessions`、`/api/v1/sessions/{session_id}/messages`、`/api/v1/sessions/{session_id}/tasks` |
| Attachment | `/api/v1/files`、`/api/v1/files/{file_id}`、`/api/v1/files/{file_id}/content` |
| Learning | `/api/v1/learning/actions`、`/api/v1/learning/attempts`、`/api/v1/learning/retests`、`/api/v1/learning/runtime/{run_id}` |
| Runtime controls | `/api/v1/tasks/{task_id}/pause`、`resume`、`cancel`、`retry`、`runtime-controls` |
| Evidence / RAG | `/api/v1/knowledge/search`、`/api/v1/knowledge/rag-search`、`/api/v1/tasks/{task_id}/events` |

OpenAPI path 全量仍以 `docs/api/openapi.json` 为唯一机器可读清单；M2 只允许 additive 变化，禁止手写第二份 TS contract。

## Task lifecycle

`TaskStatus` 当前枚举：

```text
created → queued → running
                     ├→ waiting_user → queued/running
                     ├→ waiting_review → queued/running
                     └→ completed | failed | cancelled
```

重试会创建新的 Task attempt；resume/checkpoint 继续使用现有 Runtime/Task 入口。Phase M 不改变枚举、终态集合或 checkpoint/resume 语义。

## SSE contract

SSE 从 `TaskEventModel` 按 `sequence` 升序读取，使用 `id: <sequence>`、`event: <event_type>`、JSON `data`，支持 `after` 与 `Last-Event-ID`。当前稳定事件类型包括：

```text
task.created, task.queued, task.running,
route.selected, route.reevaluated, route.unsupported,
intent.recognized, plan.created, plan.node_started, plan.node_completed,
skill.selected, tool.selected,
knowledge.query_normalized, knowledge.retrieved, knowledge.context_built,
agent.started, agent.progress, agent.input_required, agent.input_submitted,
agent.output, artifact.created,
cancel.requested, task.cancelled, task.retry_created,
task.completed, task.failed
```

基线测试覆盖 `test_sse_event_order.py`、`test_sse_events.py`、`test_sse_reconnect.py`。迁移只能改变前端消费方式，不能改变后端事件顺序和含义。

## Database

- Alembic head：`20260823_0022`
- 最新 migration：`20260823_0022_experience_memory.py`
- 该 migration 已提交；Phase M 不新增或修改 migration。

## Frontend baseline

当前 `apps/web` 是 TypeScript boundary 工具包，旧 Workspace 由 `apps/api/app/static/debug/workspace.html` + `workspace.js` 承担主业务；尚无 React/Vite shell。现有 smoke 会检查 `workspace.js` 对 `ts/materials.js`、`ts/task-transport.js`、`ts/workspace-contracts.js` 的引用。

已执行：

```text
npm run typecheck  PASS
npm run build      PASS
npm run smoke      PASS
```

## 迁移前回归

执行了 Task、SSE、attachment、math、learning、retry/resume 的聚焦回归。大部分通过；唯一已观察的 baseline failure：

```text
test_revoked_material_is_filtered_from_task_history_and_chat
```

失败发生在撤回资料历史 answer 文本断言，发生于 Phase M 代码变更之前；`GET /api/v1/tasks/{id}` 的 `revocation_notice.status=needs_review` 断言仍通过。该失败保留为 known baseline，不修改测试 expected answer，不作为前端迁移的修复范围。

## M0 冻结规则

- FastAPI routes、AgentRequest/AgentResult 公共语义、SSE sequence、Task lifecycle、checkpoint/resume、migration history 冻结。
- React 迁移采用 alternate entry → parity → default switch；旧 Workspace 在 parity 前保留。
- 后端采用 canonical owner + old-path re-export，禁止复制实现。
- M0-M8 不 commit/push；M9 统一提交。
