# Dirty Change Ownership Audit

Date: 2026-08-26
Repository: `xinzhi-daoxue`
Branch: `refactor/platform-modernization`
HEAD: `c0e68cf847aa4ccdc38299822932646210f6ee6e`
Staged changes: none
Working-tree entries: 70

## Purpose

This is an A0 read-only ownership audit. It does not decide that every dirty
file belongs in the next release, and it does not stage, delete, reset, clean,
or rewrite any change. Git does not retain authorship for uncommitted changes;
where ownership cannot be proven from the commit graph, the change remains
`UNKNOWN/REVIEW` and is not eligible for automatic release staging.

## Classification rules

| Class | Meaning | Release default |
|---|---|---|
| `LOCKDOWN` | Production execution manifest, fail-closed gates, generation fences, registry freeze, or their tests/docs | Candidate for Release A after tests |
| `WEB_FIX` | Existing non-React workspace, materials, SSE, browser launcher, or presentation compatibility work | Candidate only after browser regression |
| `SOLVER_FIX` | Solver semantic or multimodal fallback behavior | Preserve; no current dirty Solver source identified |
| `RAG_FIX` | Retrieval, context, evidence, or cache behavior | Candidate only after RAG/browser regression |
| `CIRCUIT_EXISTING` | Existing CircuitIR/renderer/harness work | Exclude from Release A unless required for baseline; Release B input |
| `TEST` | Tests, smoke checks, or generated validation outputs | Stage with the code they validate; artifacts stay out by default |
| `DOC` | Audit, architecture, plan, or handoff documents | Stage selectively with the corresponding release |
| `TEMP` | Generated artifacts or local evidence with no source-of-truth role | Do not stage automatically |
| `UNKNOWN/REVIEW` | Ownership or release intent not provable from repository evidence | Hold until human review |

## File-level ownership map

### `LOCKDOWN`

`apps/api/app/api/v1/tasks.py`; `apps/api/app/application/container.py`;
`apps/api/app/application/tasks/leases.py`;
`apps/api/app/bootstrap/lifespan.py`;
`apps/api/app/bootstrap/runtime_task_engine.py`;
`apps/api/app/core/config.py`; `apps/api/app/main.py`;
`apps/api/app/observability/architecture_telemetry.py`;
`apps/api/app/runtime/executor.py`;
`apps/api/app/runtime/handler_registry.py`;
`apps/api/app/runtime/subagents.py`;
`apps/api/app/services/context_cache.py`;
`apps/api/app/services/planner.py`;
`apps/api/app/services/rag_retrieval.py`;
`apps/api/app/services/runtime_business_registry.py`;
`apps/api/app/services/runtime_execution_boundary.py`;
`apps/api/app/services/runtime_run_lifecycle.py`;
`apps/api/app/services/runtime_task_engine.py`;
`apps/api/app/services/task_control_service.py`;
`apps/api/app/services/task_creation_service.py`;
`apps/api/app/services/task_runtime_preparation.py`;
`apps/api/app/tools/registry.py`;
`apps/api/app/services/production_execution_manifest.py`;
`apps/api/tests/test_execution_surface_lockdown.py`.

These changes implement or verify the single active execution surface. They
must be reviewed together; staging a registry fence without its manifest or
task-envelope tests is not a valid partial release.

### `WEB_FIX`

`apps/api/app/api/http_app.py`; `apps/api/app/static/debug/ts/materials.js`;
`apps/api/app/static/debug/ts/task-transport.js`;
`apps/api/app/static/debug/ts/workspace-contracts.js`;
`apps/api/app/static/debug/student.html`;
`apps/api/app/static/debug/student.js`;
`apps/api/app/static/debug/workspace-materials.js`;
`apps/api/app/static/debug/workspace-task-transport.js`;
`apps/api/app/static/debug/workspace-v2.css`;
`apps/api/app/static/debug/workspace.html`;
`apps/api/app/static/debug/workspace.js`;
`apps/web/scripts/smoke.mjs`; `scripts/team_launcher.py`.

The observed intent is to keep the original static workspace as the explicit
student surface, keep `/workspace` functional, and prevent automatic launcher
regression to the React page. This group is not accepted into Release A until
the `/workspace` browser matrix confirms answers, materials, SSE, images, and
multi-turn history remain visible.

### `TEST`

`apps/api/tests/test_config_validation.py`;
`apps/api/tests/test_debug_page.py`;
`apps/api/tests/test_student_web.py`;
`apps/api/tests/test_team_launcher.py`;
`apps/api/tests/test_unified_web_ui.py`.

These tests are coupled to `LOCKDOWN` and `WEB_FIX`. Test expectations that
only assert a historical implementation detail must be corrected narrowly,
not used to reintroduce the React or legacy execution path.

### `DOC`

`README.md`; `docs/architecture/active_execution_surface.md`;
`docs/audit/01_system_function_inventory.md` through
`docs/audit/10_scenario_stability_closeout.md`;
`docs/audit/58_execution_lockdown_baseline.md` through
`docs/audit/66_execution_surface_stable_baseline.md`;
`docs/audit/scenario_e2e_results.md`;
`docs/audit/scenario_runtime_matrix.md`;
`docs/xinzhi_answer_quality_browser_hardening/`;
`docs/xinzhi_capability_quality_hardening/`;
`docs/xinzhi_harness_maturity_circuit_v1/`;
`docs/xinzhi_tonight_global_hardening/`.

These documents are evidence and operating instructions, not executable
production code. They may be staged with a release only after their claims
match the actual test evidence.

### `TEMP`

`ci-artifacts/` is generated evidence. It is retained for inspection during
the audit but is not automatically included in the source release. It must be
handled explicitly because it can contain machine-specific paths, stale
latency, process, or task snapshots.

### `SOLVER_FIX`, `RAG_FIX`, `CIRCUIT_EXISTING`, and `UNKNOWN/REVIEW`

No uncommitted Solver source was identified; the latest Solver fallback fix is
already committed in `c0e68cf`. Retrieval/cache changes are currently part of
the `LOCKDOWN` version-fence group and must not be split from that fence.
Existing Circuit implementation history is present in committed history and
the Circuit maturity documents, but no new Circuit capability is authorized
in Release A. Any dirty change not listed above remains `UNKNOWN/REVIEW` until
the owner identifies its intent; this report does not silently assign it to a
release.

## A0 gate result

The working tree is intentionally dirty and has no staged changes. The
repository has enough evidence to proceed to RC-EXEC-01 for read-only
validation, but not enough evidence to stage or certify a release. Release A
may proceed with tests and browser inspection; Release A7 requires an explicit
human review of this map and explicit authorization to stage, commit, and tag.

## Prohibited actions during A0/A1

- `git add .`
- `git reset --hard`
- `git clean -fd`
- deleting DB, Redis, MinIO, or user task data to make a test pass
- changing the frozen `SOLVER_CT v1.0` baseline
- starting Circuit integration before Release A is certified
