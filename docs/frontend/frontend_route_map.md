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

`/student`, `/workspace-legacy`, and `/workspace-react` are compatibility redirects to `/workspace`. They do not have a separate page implementation.

## Removed legacy assets

- `student.html`/`student.js` and `workspace.html`/`workspace.js` have been deleted.
- The old Workspace adapters and generated static boundary files under `static/debug/ts/` have been deleted.
- `/workspace` serves only `react/index.html`; it contains no hidden legacy compatibility markup.
- `demo.html` is a separate scenario presentation surface; it remains outside the formal workspace.
