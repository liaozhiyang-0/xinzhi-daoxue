# Frontend parity baseline (A0)

## Current implementations

| Surface | Current entry | Implementation | Existing capabilities | Migration risk |
|---|---|---|---|---|
| Product workspace | `/workspace` | React 19 + TypeScript + Vite | Real identity/guest session, sessions, six central quick scenarios, attachments, SSE status, structured result, feedback, memory, runtime controls, resizer, independent scrolling, copy answer | Advanced input fields intentionally simplified; compatibility redirects remain for bookmarks |
| Legacy workspace | none | Removed | No separate student page implementation remains | `/student`, `/workspace-legacy`, and `/workspace-react` redirect to the React workspace |
| Teacher | `/teacher` | Vanilla JS | Learning metrics, feedback uptake, OCR/material review queues, course asset readiness | Uses a separate page shell and metric contract |
| Admin | `/admin` | Vanilla JS | Accounts, tasks, files, agents, settings, system status, audit, bounded product analytics and shared filters | Legacy page remains Vanilla JS until a later shell migration |
| Debug | `/debug/agents`, `/debug/execution`, `/debug/rag` | Vanilla JS | Agent registry, task trace, RAG inspection | `/debug/rag` now serves the dedicated RAG page |

## React P0/P1 parity target

The formal React workspace owns the supported product path:

- session create, search, archive, restore, summary, and memory;
- message history, follow-up, retry, copy, attachment preview, image preview, and document viewer;
- evidence, source navigation, context usage, and execution state;
- waiting-user and waiting-review controls;
- cancel, pause, resume, approve, and runtime input;
- feedback: resolved, satisfaction, problem type, manual review, and comment;
- research analysis options and student-attempt review.

The old Workspace source and its static generated adapters are removed. This matrix is the current route/capability baseline, not a second source of truth.
