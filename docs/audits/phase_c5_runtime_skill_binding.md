# Phase C5 Runtime Skill Binding

## Scope

C5 adds the narrow adapter between the Phase C Skill framework and the existing
Runtime handler registry. It does not add a second Runtime, checkpoint owner,
provider invocation path, or public Agent abstraction.

The binding boundary is deliberately metadata-only:

```text
CanonicalPlan.selected_skills / skill_selection
        |
        v
SkillBindingService
  - SkillRegistry resolution
  - SkillPolicy approval
  - existing RuntimeHandlerRegistry lookup
        |
        v
CanonicalPlan.skill_bindings
        |
        v
CanonicalPlanAdapter.to_runtime_plan
        |
        v
existing RuntimeNode -> PlanExecutor -> existing handler
```

## Contract changes

- `SkillBinding` identifies a stable `skill@version` to handler operation.
- `SkillExecutionDescriptor` copies the existing handler kind, risk, approval,
  replay, side-effect, and timeout policy into the plan boundary.
- `RuntimeNode`, `RuntimeNodeState`, and `RuntimeObservation` carry skill ID,
  version, and binding ID for traceability.
- Canonical-to-runtime and runtime-to-canonical adapters preserve binding
  metadata through `RuntimeGoal.context["skill_bindings"]`.

## Resolution policy

`SkillBindingService` resolves only registered and policy-approved skills. It
fails closed for an unknown skill, version mismatch, rejected planner
selection, missing prerequisite, unavailable evidence, unavailable
capability/tool/worker, or an absent/disabled existing handler.

The first concrete CT path is intentionally small: equation-system skills can
bind to the existing `linear_equation_solver` tool. The tool remains the
execution owner; C5 does not duplicate the Academic Solver or create a new
solver implementation. Worker bindings are accepted only when the caller
explicitly supplies the worker as available and the existing internal-agent
handler is registered.

Binding IDs are deterministic for `skill_id@version`, handler, and operation.
The same registered skill can therefore be reused by independent plan
contexts without creating per-request skill definitions.

## Verification

The C5 tests cover:

1. approved `CT.KCL` selection → existing equation solver handler;
2. stable reuse of the same skill in two plan contexts;
3. unknown and prerequisite-invalid selections fail closed;
4. existing `PlanExecutor` executes the bound node and carries skill metadata
   into observation and node state;
5. runtime-plan round-trip preserves the binding descriptor.

Checks run locally:

```text
44 passed, 1 skipped
Ruff: passed
Mypy: passed
```

The latest GitHub Actions backend failure was audited before C5 changes. Its
eight failing tests are in clean-checkout fixtures/runtime-launch behavior and
files outside the Phase C diff; the same run had Ruff, Mypy, and Frontend pass.
It is recorded as a baseline CI blocker, not attributed to C5.

## Boundary decision

KEEP the existing Runtime, `PlanExecutor`, `RuntimeHandlerRegistry`, tools,
workers, and Academic Solver. MERGE only the skill-to-handler decision at this
adapter boundary. Do not move provider calls into the Skill registry and do not
enable planner takeover as part of C5.
