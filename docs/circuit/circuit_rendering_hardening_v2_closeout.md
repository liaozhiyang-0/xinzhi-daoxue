# Circuit rendering hardening v2 closeout

## Scope

This change strengthens the optional circuit-drawing capability while keeping
`SOLVER_CT v1.0`, the unified ingress, planner, runtime task engine, and the
normal answer path unchanged. Circuit rendering remains a nonfatal optional
tool: invalid or unavailable drawing data cannot replace a Solver answer.

## Implementation

- Added conservative semantic adapters in `app/circuit/semantic.py`.
  - Explicit, bounded text topologies can produce trusted CircuitIR.
  - Structured VisionExtraction is accepted only with high confidence,
    explicit terminal maps, required ports, and a reference net.
  - Images are never converted from pixels or guessed coordinates.
- Unified request preparation now attaches text-derived CircuitIR only when
  the circuit renderer is explicitly requested or an enabled circuit mode is
  configured. Attachments take precedence, so multi-image requests do not
  silently fall back to text coordinates.
- Extended SchematicLayoutIR with polarity markers, direction arrows, groups,
  subcircuits, and typed annotations. The deterministic SVG renderer emits
  semantic metadata for polarity and reference arrows.
- Added explicit `CIRCUIT_RENDER_ENABLED` and `CIRCUIT_RENDER_AUTO` controls;
  the global visualization mode remains off by default.
- Added regression tests for text parsing, structured vision conversion,
  multi-image safety, layout metadata, failure isolation, large circuits, and
  feature-flag behavior.

## Verification evidence

- Browser workbench after a full service restart: health/doctor `12/12`
  passed; a typical 5 V / 1 kΩ / 2 kΩ divider task completed. The UI showed
  `电路图产物`, `已生成`, `拓扑已校验`, one SVG with viewBox `0 0 900 520`,
  and the annotation `Vout: 输出取 R2 两端`.
- Targeted circuit regression: `36 passed, 2 warnings`.
- Full project check: `2038 passed, 15 skipped, 14 warnings` in about 61
  minutes. Configuration, sensitive-file, repository-drift, Ruff, Mypy,
  OpenAPI export, Docker Compose validation, and Git whitespace checks passed.
- Exact benchmark coverage: 150 cases, 50 each for CT, AE, and DE, with the
  requested category distribution. Continuous rendering executed 750 times;
  all eight metrics were 100.0% and there were no failures.
- Frontend `npm run typecheck` and `npm run build` passed. Vite emitted only
  the existing missing debug-asset and chunk-size warnings.
- Long soak: provider-free run completed in `120.016` minutes across `3,806`
  cycles and `570,900` renders with `failure_count=0`. Python heap grew from
  `1.089 MB` to `1.397 MB`; traced heap peak grew from `1.091 MB` to
  `1.477 MB`. RSS fields were unavailable because `psutil` is not installed.
  The output digest was
  `77ea04f43174f8321476c0051c8ed5bc656c4cd9a6625f1d094e526d1fdac2f0`.
  The raw temporary evidence was written outside the repository at
  `C:\Users\86184\AppData\Local\Temp\xzd-circuit-rendering-v2-soak-20260826.json`.

## Reproduce

```powershell
$env:PYTHONPATH = 'apps/api'
.venv\Scripts\python.exe -m pytest apps/api/tests/test_circuit_semantic.py apps/api/tests/test_circuit_rendering_v2.py apps/api/tests/test_circuit_visualization_v3.py -q
.venv\Scripts\python.exe scripts/benchmark_circuit_rendering_v2.py --iterations 200
.\scripts\check.ps1
```

The benchmark is deterministic and provider-free. The browser test requires
the local services from `xzd.ps1 repair -Port 8000` and a reachable configured
model provider for the complete answer path; SVG generation itself is local
and deterministic.

## Known boundaries

- A free-form or incomplete circuit description is refused by the semantic
  adapter rather than rendered with invented topology.
- Image-derived rendering requires a trusted structured vision extraction in
  the same request context; untrusted or uncertain multi-image output remains
  a review-only observation.
- `SchematicSubcircuit` is part of the layout contract but is not populated
  unless a future semantic source supplies explicit nested topology.
- The local environment does not have `psutil`; the soak reports Python heap
  evidence and leaves RSS fields unavailable when that dependency is absent.
