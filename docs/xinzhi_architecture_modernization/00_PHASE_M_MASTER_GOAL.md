# Phase M：Frontend + Backend Architecture Modernization

## 目标
暂停 T0-T9 全量 Benchmark，先完成一次“零业务语义变化”的工程现代化：
- 前端：Vanilla JS → React + TypeScript + Vite；
- 后端：把 `services/` 中职责归位到 application / capabilities / runtime / infrastructure / governance；
- 保持 FastAPI API、SSE、Task 生命周期、Planner/Skill/Reflection/Experience/Evaluation 行为兼容；
- 不新增 public Agent、不新增第二 Runtime、不修改真实题目答案；
- Phase M 完成后从 T0 重新冻结 Benchmark 基线。

## 后端目标结构
```text
app/
├─ api/
├─ application/
│  ├─ tasks/
│  ├─ chat/
│  ├─ sessions/
│  └─ learning/
├─ agents/
│  ├─ registry/
│  ├─ routing/
│  ├─ planner/
│  └─ internal/
├─ capabilities/
│  ├─ academic_solver/
│  ├─ knowledge/
│  ├─ teaching/
│  ├─ research/
│  ├─ learning/
│  └─ general/
├─ runtime/
│  ├─ kernel/
│  ├─ execution/
│  ├─ checkpoint/
│  ├─ recovery/
│  └─ policies/
├─ infrastructure/
│  ├─ providers/
│  ├─ rag/
│  ├─ storage/
│  ├─ database/
│  └─ external/
├─ governance/
│  ├─ verification/
│  ├─ reflection/
│  ├─ experience/
│  └─ evaluation/
├─ contracts/
├─ models/
├─ bootstrap/
└─ main.py
```

这只是目标地图，不要求为了目录整齐强行搬动所有文件。

## 前端目标
```text
apps/web/
├─ src/
│  ├─ app/
│  ├─ api/
│  ├─ components/
│  ├─ features/
│  │  ├─ chat/
│  │  ├─ sessions/
│  │  ├─ tasks/
│  │  ├─ attachments/
│  │  ├─ learning/
│  │  └─ debug/
│  ├─ hooks/
│  ├─ state/
│  ├─ styles/
│  ├─ api-types.ts
│  └─ main.tsx
├─ index.html
├─ package.json
├─ tsconfig.json
└─ vite.config.ts
```

默认技术栈：React + TypeScript + Vite + fetch + EventSource + existing math renderer + generated OpenAPI types。
第一版不默认引入 Redux / Zustand / Next.js / TanStack Query / Tailwind / shadcn。

## 必须保持不变
- `POST /api/v1/tasks`
- `/api/v1/chat`
- AgentRequest / AgentResult 公共语义
- SSE 事件顺序和含义
- Task status lifecycle
- checkpoint/resume
- Planner authority
- SkillRegistry / SkillPolicy
- Tool / RAG contracts
- Reflection bounded revision
- Experience lifecycle
- Evaluation evidence levels
- public Agent IDs
- 既有 migration 历史

## 顺序
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9

## Git
M0-M8 不逐阶段 commit/push。M9 完成整个 Phase M 后统一：
```text
git diff --check
相关完整测试
git add <Phase M files only>
git commit -m "refactor(platform): complete frontend and backend modernization"
git push origin refactor/platform-modernization
GitHub Actions
remote SHA verify
```

## 完成标准
- React 成为默认 Workspace；
- 旧 `workspace.js` 不再承担主业务；
- OpenAPI generated types 为 TS 唯一 contract source；
- Session/Task/SSE/Attachment/Markdown/Math/Citation/Learning/Retry/Resume/Error parity；
- services 明显收敛但不追求 LOC KPI；
- Runtime 仍只负责执行语义，不吸收专业业务逻辑；
- 单 RuntimeTaskEngine 入口不变；
- API/SSE/DB 无破坏性变化；
- CI 状态明确；
- 完成后恢复 T0-T9，从 T0 重新冻结。
