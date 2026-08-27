# M2：React + TypeScript + Vite Shell

## 目标
先建立 React 外壳，不删除旧 Workspace。

## 必须完成
1. Vite React TS build。
2. 保持 FastAPI 静态托管兼容。
3. OpenAPI → generated TS types 流程继续工作。
4. 建立 typed API client。
5. 建立 React App shell。
6. 保留旧 Workspace 作为 parity 对照入口。
7. CI 可 build React。

## API 规则
业务组件禁止散落 `fetch()`，统一在：
```text
src/api/client.ts
src/api/tasks.ts
src/api/sessions.ts
...
```

## 默认不加入
Next.js / Redux / Zustand / TanStack Query / Tailwind / shadcn，除非仓库实际证明必要。

输出：`docs/history/frontend-react/modernization/m2_react_shell.md`

验证：npm ci、typecheck、Vite build、smoke、API type drift。
本阶段不 commit。
