# Phase M Closeout

日期：2026-08-23

## Before / after

| Area | Before | After |
| --- | --- | --- |
| Workspace | Vanilla JS was the default `/workspace` entry | React + TypeScript + Vite is default; legacy is `/workspace-legacy` |
| Frontend API | browser calls were distributed in DOM orchestration | typed `src/api/` boundary and `useTaskStream` |
| Task query/progress | implementation under `services/` | canonical owner under `application/tasks` with thin facades |
| Runtime adapters | concrete composition imported from Runtime package | canonical owner under `infrastructure`; lazy compatibility exports |
| Runtime execution | existing single engine | unchanged single `RuntimeTaskEngine` |

## Files moved or introduced

- `application/tasks/query.py` and `progress.py` are canonical task read/progress owners;
- `infrastructure/runtime_adapters.py` is the canonical adapter composition owner;
- `apps/web/src/api`, `features`, `components`, `hooks`, `app`, and Vite entry form the React shell;
- route and boundary tests protect default/legacy workspace and compatibility imports.

## Compatibility and rollback

- `/workspace-legacy` remains available;
- `/workspace-react` remains an explicit React build route;
- old Python imports remain only as thin re-export facades where import compatibility is still required;
- Task API, AgentRequest, Runtime Plan, AgentResult, RAG and Tool interfaces were not semantically changed.

## Verification

Frontend: typecheck, build and smoke are the required local checks.

Backend: focused route, adapter, subagent, skill-binding and architecture-boundary tests are the Phase M local blocking set. Full backend CI remains the remote gate.

Known baseline failure from M0 is recorded in `m7_parity_verification.md` and is outside this change.

## Deferred

Large service-by-service moves, rich Markdown/LaTeX/citation/artifact rendering, and the next full T0–T9 testing campaign are intentionally deferred. Phase M ends here; the next testing sequence is T0, but it is not started automatically.
