# M1：Frontend Feature Inventory

## Current entry

当前 Workspace 的唯一主入口是：

```text
apps/api/app/static/debug/react/index.html
  └─ apps/web/src/（React、TypeScript、Vite）
```

`apps/web/src/` 当前已有可复用的 TypeScript boundary 模块：

| 文件 | 当前 owner | 迁移目标 |
| --- | --- | --- |
| `api-types.ts` | generated OpenAPI schema | 保持 generated-only contract source |
| `workspace-contracts.ts` | payload/contract adapter | `src/api/` + feature DTO adapter |
| `task-transport.ts` | task polling/stream transport | `src/api/tasks.ts` + `hooks/useTaskStream.ts` |
| `materials.ts` | attachment selection/upload boundary | `features/attachments/` |

## Feature inventory

| Feature | React owner | React target | parity risk | move order |
| --- | --- | --- | --- | --- |
| App shell | sidebar/topbar/page shell | `app/App.tsx`、`app/layout` | low | M2 |
| Chat messages | `#messages`、answer panel | `features/chat/MessageList`、`AnswerPanel` | markdown/math/citation | M5 |
| Sessions | `#session-list`、new/search/archive | `features/sessions/` | continuity | M5 |
| Composer | `#student-form`、prompt/submit/stop | `features/chat/Composer` | task creation/attachments | M5/M6 |
| Attachments | `#image-input`、preview/material manager | `features/attachments/` | upload and extraction | M5/M7 |
| Task stream | `EventSource` in workspace/debug JS | `hooks/useTaskStream` | event order/reconnect | M6 |
| Task controls | pause/resume/approve/input/retry | `features/tasks/` | lifecycle/resume | M6/M7 |
| Evidence/citations | context evidence/source dialogs | `features/chat/EvidencePanel` | source traceability | M5 |
| Markdown/LaTeX | legacy renderer + KaTeX vendor | `components/MarkdownRenderer` | exact output safety | M5/M7 |
| Learning | hint/check/disclose/progress/retest | `features/learning/` | existing API only | M6 |
| Debug | execution/agents/RAG panels | `features/debug/` | keep separate from student app | M6/M7 |
| Error/fallback | toast/form/error notices | `components/ErrorNotice` | failure semantics | M5/M7 |

## Architectural decision

The React/Vite workspace is now the only student implementation. Compatibility routes redirect to it, and the former static Workspace source plus generated adapters are deleted. Further parity work must extend the React owner instead of recreating a second page.
