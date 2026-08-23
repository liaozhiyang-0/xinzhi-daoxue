# Frontend route map (A0)

## Formal routes

| Route | Served asset | Audience | Status |
|---|---|---|---|
| `/` | `home.html` | public | keep |
| `/login` | `login.html` | public | keep |
| `/workspace` | React build `react/index.html` | student | canonical |
| `/teacher` | `teacher.html` | teacher | keep and unify shell |
| `/admin` | `admin.html` | admin | keep and add analytics |
| `/system` | `system.html` | admin/developer | keep and unify shell |
| `/debug/agents` | `agents.html` | admin/developer | keep |
| `/debug/execution` | `execution.html` | admin/developer | keep |
| `/debug/rag` | `rag.html` | admin/developer | complete |

## Compatibility routes

`/student`, `/workspace-legacy`, and `/workspace-react` remain only as compatibility entry points during migration. They must redirect to `/workspace` after parity and regression gates pass.

## Stale assets retained for cleanup gate

- `student.html` is an older learning page and is not the asset served by `/student`.
- `workspace.html`/`workspace.js` remain as rollback and parity references until final legacy cleanup.
- `demo.html` is a separate scenario presentation surface; it remains outside the formal workspace.
