# Execution Surface Stable + Circuit Capability Release Plan

Date: 2026-08-26
Repository: `xinzhi-daoxue`
Current checkpoint: `c0e68cf847aa4ccdc38299822932646210f6ee6e`
Branch: `refactor/platform-modernization`

## 1. Objective and release separation

This plan deliberately creates two releases:

1. **Release A — Execution Surface Stable**: certify that every new task,
   restart, queue recovery, checkpoint recovery, cache lookup, browser request,
   and retry uses one current production execution chain.
2. **Release B — Circuit Capability v1**: add opt-in circuit artifacts only
   after Release A has a clean, tagged anchor.

The releases must not be combined. Release B may not change Planner ownership,
Runtime ownership, task completion semantics, Legacy Quarantine, or the stable
workspace contract. If a Circuit change requires such a change, stop and open a
new architecture review instead of extending the Circuit patch.

The invariant for both releases is:

```text
Unified Ingress
→ GoalContract
→ deterministic preflight
→ PlannerService(active)
→ Capability / Skill Binding
→ CanonicalPlan
→ TaskExecutionCoordinator / RuntimeTaskEngine
→ approved Runtime Handler / Tool / RAG / Model
→ Verification / Governance
→ Result Commit
→ SSE / Presentation
```

No legacy router, planner, runtime, provider handler, workflow, checkpoint
executor, shadow result, or fallback path may acquire production execution
authority.

## 2. Working rules

- Read `git status`, the current manifest, and the previous audit report before
  every phase.
- Make the smallest change that reuses existing contracts and registries.
- Do not rewrite Planner, Runtime, `TaskExecutionCoordinator`, Memory, or the
  frozen `SOLVER_CT v1.0` implementation.
- Do not delete legacy files, historical tasks, checkpoints, DB rows, Redis
  keys, MinIO objects, or user history to pass a test.
- Do not use `git reset --hard`, `git clean -fd`, force push, or `git add .`.
- Do not automatically commit, tag, or push. A7 requires explicit user
  authorization after all Release A gates pass.
- A failure is fail-closed. It is never permission to call a legacy fallback.
- A test result is valid only if it records command, environment, input,
  output, counters, fingerprint, and artifact location.
- If existing Solver, RAG, multimodal, memory, materials, SSE, or workspace
  behavior regresses, stop the phase and do not proceed to the next one.

## 3. Release A — Execution Surface Stable

### A0 — Dirty change ownership audit

Inputs:

```text
RELEASE_BASELINE_COMMIT = 5cb699c63bdccdfe454b12d40f399865954d2780
EXECUTION_LOCKDOWN_CHECKPOINT = c0e68cf847aa4ccdc38299822932646210f6ee6e
```

Read-only commands:

```powershell
git status
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git diff --stat
git diff --name-status
git diff --cached --stat
git ls-files --others --exclude-standard
```

Output:

```text
docs/audit/67_dirty_change_ownership.md
```

Every dirty entry must be classified as `LOCKDOWN`, `WEB_FIX`, `SOLVER_FIX`,
`RAG_FIX`, `CIRCUIT_EXISTING`, `TEST`, `DOC`, `TEMP`, or `UNKNOWN/REVIEW`.
Unknown entries are held out of release staging. A0 passes only when the owner
has reviewed the map; it does not require the tree to be clean yet.

### A1 — RC-EXEC-01 and execution identity

Record:

```text
RELEASE_BASELINE_COMMIT = 5cb699c...
EXECUTION_LOCKDOWN_CHECKPOINT = c0e68cf...
RUNTIME_GENERATION = runtime-v3
CANONICAL_PLAN_VERSION = canonical-v1
CONTROL_PLANE_VERSION = planner-v1
ACTIVE_PLANNER_OWNER = PlannerService
ACTIVE_RUNTIME_OWNER = TaskExecutionCoordinator.RuntimeTaskEngine
```

Capture a release-candidate record at:

```text
docs/audit/68_rc_exec_01_identity.md
```

The record must include build ID, Git SHA, startup fingerprint, active handler
hash, active capability hash, tool registry hash, provider mode, queue mode,
and service health. The fingerprint must be deterministic across restarts of
the same build/configuration.

Commands, using the project environment:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_execution_surface_lockdown.py -q
.\xzd.cmd doctor
.\xzd.cmd status
```

If the launcher command is unavailable, use the repository's documented
PowerShell supervisor commands and record that substitution. Docker is an
optional dependency; unavailable Docker is reported, not worked around by
deleting local state.

### A2 — Cold restart matrix

Run ten complete rounds. Each round is:

```text
stop → confirm process is gone → start → health → workspace → three tasks
```

The three tasks are:

1. ordinary question: `解释一下戴维宁定理的物理意义。`
2. text Solver: `一个10Ω电阻接在20V理想电压源两端，求电流和电阻吸收功率。`
3. a question whose answer is known to exist in the local course knowledge
   base.

For every round record:

```text
round, start/stop timestamps, HTTP health, startup fingerprint,
planner owner, runtime owner, generation, handler hash, capability hash,
task IDs, terminal status, result presence, material visibility,
legacy counters, registry drift, fingerprint mismatch
```

Output:

```text
docs/audit/69_cold_restart_matrix.md
```

Gate:

```text
10/10 tasks complete with visible results
fingerprint mismatch = 0
registry drift = 0
legacy runtime/router/handler/plan/checkpoint counters = 0
completed-without-result = 0 for this matrix
```

### A3 — Persisted state and stale execution

Do not clear any persistent service. Test these cases independently:

| Case | Setup | Required result |
|---|---|---|
| Historical session | Three related questions, restart, follow-up | Current Runtime uses correct history |
| Queued task | Leave a task queued, restart | Current-generation recovery only |
| Running/expired lease | Use a controlled fixture or existing lease test | Reconcile or requeue; never old executor |
| Old generation | Inject `runtime-v2` metadata | Migrate or reject; never execute legacy |
| Unknown handler | Canonical plan references forbidden handler | `EXECUTION_TARGET_NOT_ACTIVE` or equivalent fail-closed error |
| Old checkpoint | Read historical checkpoint | Compatibility reader → normalized current state, or terminal incompatible state |
| Retry | Retry a historical/failed task | New current-generation task, never old task resume |

Record queue namespace, task envelope, plan version, handler binding version,
checkpoint disposition, and all relevant counters in:

```text
docs/audit/70_persisted_state_generation_report.md
```

### A4 — Soak

First run a two-hour soak. Before Release A7, run a four-to-six-hour soak if
the environment supports it. Use a bounded task mix every 15–30 minutes:

```text
ordinary question → Solver → RAG → single image → multiple images
→ follow-up → new session → historical session
```

Record at each interval:

```text
fingerprint, generation, planner/runtime owner, registry hash,
handler hash, legacy counters, DB/Redis/MinIO health, memory,
task latency, running tasks, orphan tasks, expired leases
```

Output:

```text
docs/audit/71_execution_surface_soak_report.md
```

Gate: no owner drift, registry drift, legacy execution, unbounded orphan
growth, or monotonic memory growth. A timeout or infrastructure outage is an
incomplete run, not a pass.

### A5 — Browser Release Matrix

The only product acceptance surface is:

```text
http://127.0.0.1:8000/workspace
```

Minimum matrix:

| Scenario | Count | Required visible result |
|---|---:|---|
| Ordinary Q&A | 10 | Answer, progress, terminal state |
| Text Solver | 10 | Structured reasoning/result |
| Single-image Solver | 8 | Image retained and answer visible |
| Multi-image Solver | 5 | All intended inputs retained |
| RAG | 5 | Answer plus material evidence card |
| Multi-turn sessions | 5 sessions × 8–15 turns | History and follow-up context preserved |
| Restart recovery | 5 | Continue after API restart |

For each case record task ID, input/material count, SSE sequence, terminal
status, answer text, evidence/material rendering, image rendering, console
errors, network failures, latency, and whether a manual review was requested.

Output:

```text
docs/audit/72_workspace_release_matrix.md
```

### A6 — Final Release Gate

Run the narrowest available project gate first:

```powershell
.\scripts\check.ps1
```

If the wrapper is unavailable, run and record separately:

```powershell
& .\.venv\Scripts\ruff.exe check <changed-python-files>
& .\.venv\Scripts\python.exe -m pytest <lockdown-and-runtime-tests> -q
node --check apps/api/app/static/debug/workspace.js
& .\.venv\Scripts\python.exe -m pytest apps/api/tests/test_config_validation.py -q
git diff --check
```

Minimum coverage areas:

```text
manifest, bootstrap preflight, registries, Runtime boundary,
TaskExecutionCoordinator, Planner, queue/lease, checkpoint, retry,
SSE, workspace, knowledge QA, Solver, multimodal, memory/session
```

Output:

```text
docs/audit/73_execution_surface_release_gate.md
```

The gate must explicitly list passed, failed, skipped, unavailable, and not
run. Mypy or Docker absence must never be silently counted as passed.

### A7 — Human-authorized Git release

A7 is blocked until A0–A6 pass and the user approves the staged file list.
Stage by category, never with `git add .`:

```powershell
git add <reviewed-lockdown-files>
git add <reviewed-web-files>
git add <reviewed-tests>
git add <reviewed-docs>
git diff --cached --stat
git diff --cached
```

Exclude `TEMP`, `UNKNOWN/REVIEW`, secrets, student privacy, and unrelated
generated artifacts. Only after explicit authorization:

```powershell
git commit -m "chore(runtime): certify locked production execution surface"
git rev-parse HEAD
git tag -a execution-surface-stable-v1 -m "Certified locked production execution surface"
git show execution-surface-stable-v1 --stat
```

Do not push automatically. After tag creation, perform one final start →
health → `/workspace` smoke test and record the result. This tag is the only
approved starting point for Release B.

## 4. Release B — Circuit Capability v1

Release B starts from a clean worktree at `execution-surface-stable-v1`:

```powershell
git switch -c feature/circuit-capability-v1 execution-surface-stable-v1
git status
```

If the tree is not clean, stop. Do not carry the 70-entry checkpoint into
Circuit development.

### B0/B1 — Standalone Circuit pipeline

Validate only:

```text
CircuitIR → schema validation → topology validation → layout → SVG artifact
```

Use a 30-case golden set: 10 easy, 10 medium, 10 hard. Human ground truth
must include component list/value, node and branch relations, source polarity,
and directions. Measure Component Recall, Component Accuracy, Node Accuracy,
Branch Accuracy, Direction Accuracy, and Render Success.

### B2 — Feature flags and baseline protection

Default configuration:

```env
CIRCUIT_RENDER_ENABLED=false
CIRCUIT_RENDER_AUTO=false
```

With both flags off, rerun the Release A browser matrix. Results must match
the stable tag for answer quality, latency within the accepted baseline,
materials, SSE, history, and all Legacy counters.

### B3/B4/B5 — Explicit ON and adapter

Support only explicit user requests first. Reuse existing vision observations
and Solver structured facts; do not call Vision twice for the same image.
Accept adapters from text, existing image observations, and derived-equivalent
circuit facts.

Apply:

```text
CircuitIR → schema validation → topology validation
```

with states `VALIDATED`, `UNCERTAIN`, and `INVALID`:

- `VALIDATED`: render normally.
- `UNCERTAIN`: render only as an explicitly marked schematic with assumptions.
- `INVALID`: do not render; keep the Solver answer successful.

### B6/B7 — Artifact and workspace presentation

Persist SVG through the existing artifact path:

```text
Renderer → MinIO/artifact store → artifact_ref → SSE/result presentation
```

Do not put SVG XML into answer text or an in-memory-only result. `/workspace`
must display the answer first and the circuit artifact separately, with an
uncertainty notice when applicable.

### B8/B9 — Browser and failure injection

Run at least 40 explicit-on cases: text-to-drawing 10, image redraw 10,
equivalent circuit 5, small-signal 5, multi-image 5, blurry/uncertain 5.
Inject CircuitIR, validator, renderer, and artifact failures independently.
The Solver result must remain successful where its own contract succeeds; only
the circuit artifact may degrade to a clear unavailable message.

### B10/B11 — Conservative AUTO

Enable AUTO only after explicit-on and failure-injection gates pass. Initial
AUTO triggers are limited to Thevenin, Norton, small-signal equivalents,
explicit op-amp feedback structures, and unambiguous equivalent-circuit
requests. Benchmark 20 expected-trigger and 20 expected-no-trigger cases;
record true positives, false positives, and false negatives. Optimize for low
user interruption, not maximum trigger rate.

### B12/B13 — Circuit release gate and commits

Rerun the full Release A matrix and compare against the stable tag. Required:

```text
normal Solver quality >= stable baseline
Circuit OFF latency ≈ stable baseline
legacy invocation = 0
runtime/registry drift = 0
```

Use small reversible commits, for example:

```text
test(circuit): certify standalone circuit pipeline
feat(circuit): add opt-in circuit rendering capability
feat(circuit): add validated circuit ir adapter
feat(circuit): persist svg circuit artifacts
feat(web): present circuit render artifacts
feat(circuit): add conservative automatic render policy
```

Do not merge or push automatically.

## 5. Stop conditions and rollback

Stop the current phase immediately if any of the following occurs:

- legacy counter becomes non-zero;
- active owner, handler hash, capability hash, or fingerprint drifts;
- a task completes without a visible result;
- a stale task reaches a legacy executor;
- existing Solver, RAG, multimodal, memory, materials, SSE, or workspace
  behavior regresses;
- Circuit failure changes Solver task status or result;
- a test passes only after clearing persistent state.

During Release A, rollback means preserving the dirty tree and returning to
the user-selected baseline only through an explicit, reviewed Git operation;
this plan never runs destructive reset/clean commands. After Release A is
tagged, Circuit rollback should normally be a revert of the smallest Circuit
commit, leaving the stable execution-surface tag intact.

## 6. Required phase reports

| Phase | Report |
|---|---|
| A0 | `docs/audit/67_dirty_change_ownership.md` |
| A1 | `docs/audit/68_rc_exec_01_identity.md` |
| A2 | `docs/audit/69_cold_restart_matrix.md` |
| A3 | `docs/audit/70_persisted_state_generation_report.md` |
| A4 | `docs/audit/71_execution_surface_soak_report.md` |
| A5 | `docs/audit/72_workspace_release_matrix.md` |
| A6 | `docs/audit/73_execution_surface_release_gate.md` |
| B0–B1 | Existing Circuit standalone report, updated with current golden-set evidence |
| B2–B12 | Circuit reports under `docs/audit/` and `docs/circuit/` |

Every report must state changed files, commands, environment, inputs, outputs,
passed/failed/skipped tests, browser evidence, execution fingerprint, legacy
counters, remaining risks, and the condition for entering the next phase.
