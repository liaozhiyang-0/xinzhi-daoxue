# M2：React + TypeScript + Vite Shell

日期：2026-08-23

## 已完成

- `apps/web` 已切换为 React + TypeScript + Vite 构建链。
- 保留原 `npm run typecheck`、`npm run build`、`npm run smoke`；build 现在先生成旧 TS boundary，再生成 Vite bundle。
- 建立 `src/api/client.ts`，统一 JSON/FormData 请求、错误解析和 HTTP 状态处理。
- 建立 `src/api/tasks.ts`、`sessions.ts`、`attachments.ts`、`learning.ts`，业务组件不直接散落 `fetch()`。
- 建立 `hooks/useTaskStream.ts`，按既有事件名订阅 SSE，使用 EventSource 原生重连和 cleanup，不修改服务端 event sequence。
- 建立 React App shell、SessionList、MessageList、Composer、MarkdownRenderer、TaskStatus。
- Vite 输出到 `apps/api/app/static/debug/react/`，FastAPI 新增 `/workspace-react` 与 `/react-assets` alternate entry。
- React 已成为 `/workspace` 默认入口；旧实现通过 `/workspace-legacy` 保持为 parity 对照和 rollback 入口。

## 目录

```text
apps/web/
├─ src/
│  ├─ api/                 # typed API boundary
│  ├─ app/App.tsx          # shell + orchestration only
│  ├─ components/          # presentation primitives
│  ├─ features/chat/       # message/composer
│  ├─ features/sessions/   # session list
│  ├─ hooks/useTaskStream.ts
│  ├─ styles/app.css
│  └─ main.tsx
├─ index.html
└─ vite.config.ts
```

## Contract decisions

1. React 使用 `StudentTaskPayload` 适配既有 `AgentRequest`，不重新定义 Task/Agent 业务语义。
2. `createTask` 仍调用 `POST /api/v1/tasks`，任务完成仍通过 `GET /api/v1/tasks/{id}` 获取完整结果。
3. `useTaskStream` 只消费现有事件名；`task.completed/failed/cancelled` 触发结果刷新，其余事件只进入 UI 过程列表。
4. 上传仍走 `/api/v1/files`，learning API 单独保留在 `src/api/learning.ts`，不复制后端学习逻辑。
5. Markdown 首版保留安全纯文本展示边界；M5 再接入既有数学渲染器和 citation/source presentation，不在 M2 引入新的渲染依赖。

## 验证

```powershell
npm --prefix apps/web install
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/web run smoke
pytest apps/api/tests/test_react_workspace_route.py -q
```

当前结果：typecheck PASS、Vite build PASS、legacy + React smoke PASS。默认入口切换在 M8 完成，旧入口仍可显式回滚。
