# Circuit Stress Report — Release B controlled slice

Date: 2026-08-26
Branch: `feature/circuit-capability-v1`
Release anchor: `user-resilient-stable-v1` → `fb88cafa07b2ed3179b9a55e1b5470a950dfeb1a`

## Executed checks

| Check | Result |
|---|---:|
| Circuit core + Release B unit suite | 31 passed, 2 warnings |
| Circuit + legacy workspace UI suite | 43 passed, 2 warnings |
| Failure/mode/dependency injection subset | 3 passed, 7 deselected, 2 warnings |
| Controlled real task | completed |
| Browser reload/history artifact card | passed |
| Circuit OFF Release A focused regression | 72 passed, 8 skipped, 2 warnings |

## Controlled task evidence

Task `task_5622b858f7604d1b999567754ba846fd` entered the existing
`PlannerService → CanonicalPlan → AcademicSolverRuntimeService` path. The
canonical plan selected `circuit.render`; the task persisted a structured
result and a `circuit_svg` artifact. The result reported
`validation_state=validated` and retained renderer warnings rather than
failing the solver.

After page reload and history selection at `/workspace`, the browser DOM
contained the independent circuit panel, `panelHidden=false`, one inline SVG,
and the visible states `降级生成` / `拓扑已校验`.

## Failure policy

The failure-injection tests confirm that renderer failure and unavailable
dependencies become bounded nonfatal observations. The solver answer remains
the primary result. Invalid or uncertain CircuitIR is not silently turned into
an executable drawing.

## Scope limits

- The current repository fixture has 13 golden topologies, not the planned 50.
- The current B slice consumes trusted structured CircuitIR; it does not infer
  CircuitIR from an image in the Planner.
- AUTO was not enabled by this Release B change.
- The repository 8+ hour mixed browser soak and final quality matrix remain
  separate gates; this report does not certify `LONG_RUN_STABLE`.
