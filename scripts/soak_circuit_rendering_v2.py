"""Run a provider-free CircuitIR rendering soak with bounded memory evidence.

The soak exercises the same deterministic validation, layout, rendering and
observation projection used by the circuit capability.  It never calls a
model, stores SVG payloads, or mutates the application database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rss_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return None
    return round(psutil.Process(os.getpid()).memory_info().rss / 1024**2, 3)


def _heap_mb() -> tuple[float, float]:
    current, peak = tracemalloc.get_traced_memory()
    return round(current / 1024**2, 3), round(peak / 1024**2, 3)


def run(duration_minutes: float, sample_interval_seconds: float) -> dict[str, Any]:
    from app.circuit import CircuitRenderOptions, build_schematic_layout, render_circuit
    from app.circuit.validator import validate_circuit
    from app.services.circuit_visualization import observation_from_result

    from scripts.benchmark_circuit_rendering_v2 import coverage_cases

    tracemalloc.start()
    cases = coverage_cases()
    started = time.monotonic()
    deadline = started + duration_minutes * 60
    sample_interval = max(1.0, sample_interval_seconds)
    next_sample = started
    initial_rss = _rss_mb()
    max_rss = initial_rss
    initial_heap, initial_heap_peak = _heap_mb()
    max_heap = initial_heap
    max_heap_peak = initial_heap_peak
    samples: list[dict[str, float | int | None]] = []
    cycles = 0
    render_count = 0
    failures: list[dict[str, str]] = []
    digest = hashlib.sha256()

    while time.monotonic() < deadline or cycles == 0:
        for case in cases:
            validation = validate_circuit(case.circuit)
            result = render_circuit(
                case.circuit, CircuitRenderOptions(template=case.template)
            )
            if validation.status != "validated" or result.svg is None:
                failures.append(
                    {
                        "course": case.course,
                        "category": case.category,
                        "status": result.status,
                    }
                )
                continue
            build_schematic_layout(case.circuit, case.template)
            observation = observation_from_result(case.circuit, result)
            digest.update((result.svg or "").encode("utf-8"))
            digest.update(observation.renderer.encode("utf-8"))
            render_count += 1
        cycles += 1
        now = time.monotonic()
        if now >= next_sample:
            rss = _rss_mb()
            max_rss = max(max_rss or 0.0, rss or 0.0) if rss is not None else max_rss
            heap, heap_peak = _heap_mb()
            max_heap = max(max_heap, heap)
            max_heap_peak = max(max_heap_peak, heap_peak)
            samples.append(
                {
                    "elapsed_seconds": round(now - started, 3),
                    "cycle": cycles,
                    "rss_mb": rss,
                    "heap_mb": heap,
                    "heap_peak_mb": heap_peak,
                }
            )
            next_sample = now + sample_interval
        if now >= deadline:
            break

    elapsed = max(0.0, time.monotonic() - started)
    return {
        "schema_version": "circuit_rendering_v2_soak.v1",
        "provider_free": True,
        "coverage_cases": len(cases),
        "duration_requested_minutes": duration_minutes,
        "duration_observed_minutes": round(elapsed / 60, 3),
        "cycles": cycles,
        "render_count": render_count,
        "failures": failures[:64],
        "failure_count": len(failures),
        "rss_initial_mb": initial_rss,
        "rss_max_mb": max_rss,
        "rss_delta_mb": (
            round(max_rss - initial_rss, 3)
            if initial_rss is not None and max_rss is not None
            else None
        ),
        "heap_initial_mb": initial_heap,
        "heap_max_mb": max_heap,
        "heap_peak_initial_mb": initial_heap_peak,
        "heap_peak_max_mb": max_heap_peak,
        "heap_delta_mb": round(max_heap - initial_heap, 3),
        "samples": samples,
        "output_digest": digest.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-minutes", type=float, default=120.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=60.0)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.duration_minutes <= 0:
        parser.error("--duration-minutes must be positive")
    report = run(args.duration_minutes, args.sample_interval_seconds)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if report["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
