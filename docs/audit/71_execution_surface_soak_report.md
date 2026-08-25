# Release A4 execution-surface soak

Date: 2026-08-26
Status: **INTERRUPTED LONG-CANDIDATE — 16/16 cycles passed; full 2-hour gate not completed by instruction**

## Harness correction

The existing `scripts/run_e2e_soak.py` was still asserting a React asset
surface and posting to `/api/v1/chat`. That was incompatible with the current
legacy workspace and the locked task boundary. The harness was updated to
check `/workspace` plus KaTeX/UI/workspace assets and to create non-blocking
tasks through `POST /api/v1/tasks`.

The old pre-correction run is retained at
`.codex-tmp/release-a-soak-once.jsonl` as a rejected harness result; it is not
counted as a production failure.

## Corrected one-cycle evidence

Command:

```powershell
& .\.venv\Scripts\python.exe scripts/run_e2e_soak.py `
  --once --research-every 0 --poll-timeout-seconds 180 `
  --log .codex-tmp/release-a-soak-current-once-v4.jsonl
```

Surface checks:

- health: HTTP 200, `status=ok`
- `/workspace`: HTTP 200
- KaTeX, `ui-core.js`, `workspace.js`, and `workspace-v2.css`: HTTP 200
- `frontend_build_ready=true`
- task ingress: `POST /api/v1/tasks`, HTTP 202 for accepted cases

Task outcomes in the corrected cycle after the academic-writing binding fix:

- 10 enabled cases reached their declared contract: nine ordinary cases
  completed with non-empty results, and `lesson_preparation` correctly reached
  either `completed` or its explicit `waiting_review` checkpoint. Academic
  writing used the current Planner/Runtime surface.
- 1 data-analysis case was rejected with HTTP 409 because the repository's
  data-analysis capability is explicitly frozen by configuration; the harness
  now records this as an expected `blocked_by_configuration` outcome.
- process exit was `0`; no unclassified failures were recorded.
- cycle elapsed time was approximately 124 seconds.

Evidence:

```text
.codex-tmp/release-a-soak-current-once-v4.jsonl
```

## Interpretation

The task boundary, current Runtime, RAG-backed concepts, academic writing,
teaching prep, assignment review, ordinary answers, and the legacy workspace
all satisfied their declared short-gate contracts. The teaching-prep
`waiting_review` state is an approval checkpoint, not an empty-answer failure.
The academic-writing correction was a
shared capability-binding registration in the authoritative Planner; it did
not restore `/api/v1/chat` or enable a legacy fallback.

The data-analysis 409 is an explicit frozen-feature policy and is recorded as
`blocked_by_configuration`, not as a legacy execution failure. It must remain
out of the stable gate unless the release owner explicitly re-enables that
capability in a separate, reviewed change.

## Long soak status

1. Keep the frozen data-analysis 409 as an explicit release exclusion; do not
   re-enable it in Release A.
2. The v8 candidate was stopped after four cycles because browser inspection
   found malformed evidence formulas; the shared renderer was then corrected.
3. The v9 candidate was stopped after six cycles because the harness treated a
   valid completed retrieval with an explicit no-evidence refusal as a failure.
   The harness contract was corrected narrowly and a short research-inclusive
   cycle passed.
4. The corrected v10 candidate was run with:

   ```powershell
   & .\.venv\Scripts\python.exe scripts/run_e2e_soak.py `
     --duration-seconds 7200 --interval-seconds 300 --research-every 6 `
     --poll-timeout-seconds 180 `
     --log .codex-tmp/release-a-soak-2h-v10.jsonl
   ```

   It was intentionally interrupted by the release owner after 16 cycles.
   All 16 cycles passed, including the research-inclusive cycle 6; each cycle
   checked health, `/workspace`, KaTeX/UI/workspace/CSS assets, the local task
   cases, and the expected frozen data-analysis 409. No legacy execution or
   surface failure was recorded in the harness output.

   This is strong long-run evidence, but it is not a completed 7200-second
   soak and therefore is not independently sufficient to claim the full A4
   two-hour gate. Release A7 proceeds here by explicit owner authorization.

Evidence:

```text
.codex-tmp/release-a-soak-2h-v10.jsonl
```
