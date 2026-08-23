# Frontend parity baseline (A0)

## Current implementations

| Surface | Current entry | Implementation | Existing capabilities | Migration risk |
|---|---|---|---|---|
| Product workspace | `/workspace` | React 19 + TypeScript + Vite | Real identity/guest session, sessions, six central quick scenarios, attachments, SSE status, structured result, feedback, memory, runtime controls, resizer, independent scrolling, copy answer | Legacy document/image viewer remains a migration comparison surface; advanced input fields intentionally simplified |
| Legacy workspace | `/student`, `/workspace-legacy` | Vanilla JS + `workspace.html` | Session search/archive, memory, evidence/context tabs, source navigation, image/document viewers, feedback, research options, runtime controls | Compatibility assets remain during final parity/cleanup gate; no longer a formal entry |
| Teacher | `/teacher` | Vanilla JS | Learning metrics, feedback uptake, OCR/material review queues, course asset readiness | Uses a separate page shell and metric contract |
| Admin | `/admin` | Vanilla JS | Accounts, tasks, files, agents, settings, system status, audit, bounded product analytics and shared filters | Legacy page remains Vanilla JS until a later shell migration |
| Debug | `/debug/agents`, `/debug/execution`, `/debug/rag` | Vanilla JS | Agent registry, task trace, RAG inspection | `/debug/rag` now serves the dedicated RAG page |

## React P0/P1 parity target

The formal workspace must own the following behavior before the legacy implementation is removed:

- session create, search, archive, restore, summary, and memory;
- message history, follow-up, retry, copy, attachment preview, image preview, and document viewer;
- evidence, source navigation, context usage, and execution state;
- waiting-user and waiting-review controls;
- cancel, pause, resume, approve, and runtime input;
- feedback: resolved, satisfaction, problem type, manual review, and comment;
- research analysis options and student-attempt review.

The formal React workspace now covers the product P0/P1 path. Legacy-only document/image navigation remains available as a compatibility reference and is not deleted in this phase. This matrix is a baseline and migration gate, not a second source of truth.
