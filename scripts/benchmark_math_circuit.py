"""Record a reproducible local performance baseline for the overnight core."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.circuit import (  # noqa: E402
    CircuitIR,
    CircuitRenderOptions,
    render_circuit,
    validate_circuit,
)
from app.services.math_formatting_service import MathFormattingService  # noqa: E402
from audit_math_corpus import _formula_tokens, _iter_sources  # noqa: E402


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[
        int(quantile * 100) - 1
    ]


def run(source_root: Path, output_root: Path) -> dict[str, object]:
    scan_started = perf_counter()
    formulas: list[str] = []
    for _, path in _iter_sources(source_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        tokens, _ = _formula_tokens(text)
        formulas.extend(body for _, _, body in tokens)
    scan_ms = (perf_counter() - scan_started) * 1000

    formatter = MathFormattingService()
    normalization_ms: list[float] = []
    for formula in formulas:
        started = perf_counter()
        formatter.normalize_latex(formula)
        normalization_ms.append((perf_counter() - started) * 1000)

    fixture_path = (
        output_root
        / "apps"
        / "api"
        / "tests"
        / "fixtures"
        / "circuit_golden_cases.json"
    )
    fixture_cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    validation_ms: list[float] = []
    render_ms: list[float] = []
    svg_sizes: list[int] = []
    for case in fixture_cases:
        circuit = CircuitIR.model_validate(
            {key: case[key] for key in ("components", "nets")}
        )
        started = perf_counter()
        validate_circuit(circuit)
        validation_ms.append((perf_counter() - started) * 1000)
        started = perf_counter()
        result = render_circuit(
            circuit, CircuitRenderOptions(template=str(case["template"]))
        )
        render_ms.append((perf_counter() - started) * 1000)
        svg_sizes.append(len(result.svg or ""))

    baseline: dict[str, object] = {
        "schema_version": "math_circuit_performance.v1",
        "source_root": str(source_root),
        "math_formula_count": len(formulas),
        "corpus_scan_ms": round(scan_ms, 3),
        "math_normalization_ms": {
            "p50": round(percentile(normalization_ms, 0.50), 5),
            "p95": round(percentile(normalization_ms, 0.95), 5),
            "max": round(max(normalization_ms, default=0), 5),
        },
        "circuit_fixture_count": len(fixture_cases),
        "circuit_validation_ms": {
            "p50": round(percentile(validation_ms, 0.50), 5),
            "p95": round(percentile(validation_ms, 0.95), 5),
        },
        "svg_render_ms": {
            "p50": round(percentile(render_ms, 0.50), 5),
            "p95": round(percentile(render_ms, 0.95), 5),
        },
        "svg_size_bytes": {
            "min": min(svg_sizes, default=0),
            "max": max(svg_sizes, default=0),
            "mean": round(statistics.mean(svg_sizes), 2) if svg_sizes else 0,
        },
        "network_simulation": False,
        "external_provider_calls": 0,
    }
    output_path = (
        output_root / "evaluation" / "math_circuit" / "performance_baseline.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = "\n".join(
        [
            "# Math and circuit performance baseline",
            "",
            f"- formulas normalized: `{len(formulas)}`",
            f"- corpus scan: `{scan_ms:.2f} ms`",
            "- math normalize p50/p95: "
            f"`{baseline['math_normalization_ms']['p50']}` / "
            f"`{baseline['math_normalization_ms']['p95']} ms`",
            f"- circuit fixtures: `{len(fixture_cases)}`",
            "- CircuitIR validation p50/p95: "
            f"`{baseline['circuit_validation_ms']['p50']}` / "
            f"`{baseline['circuit_validation_ms']['p95']} ms`",
            "- SVG render p50/p95: "
            f"`{baseline['svg_render_ms']['p50']}` / "
            f"`{baseline['svg_render_ms']['p95']} ms`",
            "- SVG bytes min/max: "
            f"`{min(svg_sizes, default=0)}` / `{max(svg_sizes, default=0)}`",
            "",
            "This is a local CPU baseline only. It is not a throughput or "
            "production capacity claim; "
            "no simulation, network call, model call, or full C5 benchmark was run.",
            "",
        ]
    )
    report_path = output_root / "docs" / "circuit" / "performance_baseline.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8", newline="\n")
    return baseline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.source_root.resolve(), args.output_root.resolve()),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
