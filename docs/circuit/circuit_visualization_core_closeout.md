# Circuit visualization core closeout

## Delivered

- Added Pydantic `CircuitIR v1` contracts for components, ports, nets, annotations, provenance, assumptions, and uncertainties.
- Added deterministic NetworkX topology validation for unsupported types, port/net references, missing ports, duplicate IDs, floating/disconnected topology, output-output shorts, and critical uncertainty.
- Added a SchemDraw renderer path with deterministic SVG fallback; renderer failures return a nonfatal result instead of raising into the answer path.
- Added disabled-by-default `circuit.render` tool registration and JSON-safe tool handling.
- Added 13 golden fixtures covering R/L/C, independent and dependent sources, op-amp, diode, BJT, and MOSFET schemas.

## Evidence

- SchemDraw 0.21 was installed only into a temporary verification directory and generated an SVG successfully (`rendered/schemdraw`). The shared virtual environment was not modified.
- The normal shared environment exercises the deterministic fallback because SchemDraw is not installed there; this is reported as `degraded`, not as a silent success.
- Circuit performance baseline: 13 fixtures; validation p50/p95 `0.0865/0.61194 ms`; fallback SVG p50/p95 `0.4488/1.21052 ms`; SVG size range `1260–2115` bytes.
- No simulation, netlist generation, external provider call, or frontend dependency was added.

## Reproduce

```powershell
$py = 'C:\Users\86184\Desktop\xinzhi-daoxue\.venv\Scripts\python.exe'
& $py scripts\benchmark_math_circuit.py --source-root 'C:\Users\86184\Desktop\xinzhi-daoxue' --output-root 'C:\Users\86184\Desktop\xinzhi-math-circuit-night'
& $py -m pytest apps/api/tests/test_circuit_core.py -q
```

The benchmark is a local CPU baseline only and must not be read as a production throughput guarantee.
