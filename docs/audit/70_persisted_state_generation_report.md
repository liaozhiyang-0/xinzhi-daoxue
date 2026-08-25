# Release A3 Persisted State and Generation Report

Date: 2026-08-26
Runtime generation: `runtime-v3`
Canonical plan: `canonical-v1`

## Automated evidence

The following focused group completed successfully:

```text
39 passed, 8 skipped, 2 warnings
duration: 363.72s
```

Covered areas include execution-surface metadata fences, forbidden canonical
targets, runtime checkpoint control data, Knowledge QA persistence recovery,
Runtime task execution and handoff, event sequence, and Agent/session
foundations. The skipped cases are recorded by the test suite and are not
counted as passed recovery scenarios.

## Real persisted Session recovery

| Step | Result |
|---|---|
| Create Session | `session_530f29a7cd384a6699405360c5d55225` |
| First task | `task_25eafa7131004b949f81286077b77b11`, completed, result present |
| Full stop/start | completed; DB/Redis/MinIO/Qdrant data volumes retained |
| Follow-up task | `task_466e5e0c44e14265b6723e4083eb56fe`, completed, result present |
| Follow-up generation | `runtime-v3` |
| Follow-up fingerprint | `d718d3f3de80ccc36b13687b5dc29664f55da23ddde778c1e7d03f2216c32f96` |

The follow-up remained on the current Runtime after restart. The first task's
history was available to the Session path; no legacy Runtime was invoked.

## Fail-closed coverage

The lockdown test group verifies that:

- stale task metadata with `runtime-v2` is rejected;
- an unknown/forbidden handler is rejected;
- a `legacy-runtime:*` plan is rejected;
- current task metadata carries build, generation, plan, handler, capability,
  and startup fingerprint values;
- retry metadata is fenced by the active manifest.

The current live point-in-time counters after recovery were zero for legacy
runtime/router/handler/plan/checkpoint invocation, execution-target rejection,
registry drift, and fingerprint mismatch.

## Remaining A3 proof gaps

The following are not claimed as fully manually certified by this report:

- a real queued task surviving restart;
- an artificially expired running lease surviving restart;
- a real stale-generation DB task migration or terminal rejection;
- a real historical checkpoint that cannot be safely normalized;
- browser-visible retry of a historical task.

These cases remain required before the Release A3 gate can be closed. No data
was deleted or rewritten to obtain the results above.
