# Release B — Circuit Capability v1

Date: 2026-08-26
Branch: `feature/circuit-capability-v1`
Anchor: `user-resilient-stable-v1` → `fb88cafa07b2ed3179b9a55e1b5470a950dfeb1a`

## Scope

Release B is opt-in and attaches to the existing Planner → CanonicalPlan →
RuntimeTaskEngine chain. It does not create a second executor, change Solver
ownership, enable a legacy path, or change task completion semantics.

The existing standalone pipeline is:

```text
CircuitIR → deterministic validation → layout → SVG artifact
```

The default configuration remains `CIRCUIT_VISUALIZATION_MODE=off`. Explicit
controlled mode is required before a circuit node can be scheduled.

## B0/B1 standalone baseline

Existing CircuitIR, validator, layout, renderer, tool, and runtime projection
tests passed from the Release A tag:

```text
30 passed, 2 warnings
```

The repository fixture currently contains 13 golden topologies. This is below
the planned 30-case human-ground-truth set and remains an explicit quality
gap; no fabricated 30-case result is claimed.

## B2/B3/B4 implementation

- Feature mode remains fail-closed by default.
- `controlled` mode schedules only when explicit circuit intent and trusted
  structured `circuit_ir` are both present.
- Invalid or uncertain CircuitIR remains a nonfatal nested observation; the
  Solver answer is not replaced by a circuit failure.
- The existing artifact commit path persists the `circuit_svg` artifact and
  its structured observation with the task result.
- `/workspace` now renders a separate circuit artifact card, inline from the
  persisted structured result, with validation state, warnings, and a safe SVG
  parser that strips scripts, `foreignObject`, event attributes, and
  `javascript:` hrefs.

## B5/B6/B7 verification completed for the controlled scope

The real controlled-mode task used the existing AE workspace session and a
trusted CircuitIR:

- task: `task_5622b858f7604d1b999567754ba846fd`;
- planner decision: `REQUIRED`, reason `explicit_draw_request`;
- selected tool: `circuit.render`;
- terminal status: `completed`;
- durable artifacts: one `structured_result` and one `circuit_svg`;
- structured result: `validation_state=validated`, `status=degraded`, SVG
  present, warnings preserved;
- browser reload/history check: `/workspace` displayed the separate circuit
  card with `panelHidden=false`, one inline SVG, `降级生成`, and `拓扑已校验`.

The bounded failure-injection cases also passed: renderer failure and missing
dependency are represented as nonfatal observations, while the solver result
remains usable. No invalid circuit path is allowed to replace the answer.

Verification executed after the final B wiring:

```text
test_circuit_core.py + test_circuit_visualization_v3.py: 31 passed, 2 warnings
test_circuit_visualization_v3.py + test_unified_web_ui.py: 43 passed, 2 warnings
failure/mode/dependency subset: 3 passed, 7 deselected, 2 warnings
Release A focused regression with Circuit OFF: 72 passed, 8 skipped, 2 warnings
```

The service was then restarted with `CIRCUIT_VISUALIZATION_MODE=off` and left
in that default production posture. The separate controlled task was run
before this final OFF restart.

The repository-wide prescribed check also completed its non-test stages:
configuration, sensitive-file scan, repository-drift scan, Ruff, Mypy,
OpenAPI export, Docker Compose validation, and `git diff --check` passed.
The full 2,021-test run produced `1,997 passed, 15 skipped, 9 failed`; the
failures are outside the B circuit suites and include the pre-existing React
default-route expectation, dynamic registry registration against the locked
registry, and several state/debug contracts. They are retained as known
baseline failures and are not presented as a green full-suite result.

The bounded real E2E cycle (`.codex-tmp/release-b-final-e2e.jsonl`) recorded 11
tasks, 10 completed and one expected configuration rejection, with zero cycle
failures. The legacy workspace and KaTeX asset checks all returned HTTP 200.

## Current risks

- Real image-to-CircuitIR extraction is not auto-created by the Planner; it
  must be supplied by the existing trusted structured observation path.
- The golden fixture is 13 cases, not the planned 30 cases.
- A4 was owner-interrupted at 16/16 passing cycles before 7200 seconds; this
  is evidence, not a full two-hour certification.
- The repository-level 8+ hour browser/mixed soak gate from
  `docs/xinzhi_8h_soak_boundary_quality_v1/` is not certified by these short
  runs; no `LONG_RUN_STABLE` claim is made here.
