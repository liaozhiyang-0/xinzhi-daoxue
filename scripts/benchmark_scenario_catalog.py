from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


def benchmark(iterations: int) -> dict[str, object]:
    from app.contracts.agent import AgentRequest  # type: ignore[import-untyped]
    from app.contracts.orchestration import (  # type: ignore[import-untyped]  # noqa: I001,E501
        AgentRequestV2,
        CourseCode,
    )
    from app.services.scenario_catalog import (  # type: ignore[import-untyped]
        ScenarioCatalog,
    )

    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    request = AgentRequestV2(
        message="生成课程设计",
        course_hint=CourseCode.CT,
        scenario_id="faculty_course_copilot_v1",
    )
    legacy_request = AgentRequest(
        session_id="benchmark-session",
        user_id="benchmark-user",
        course_id="CT",
        scenario_id="faculty_course_copilot_v1",
        options={"input_type": "text"},
    )

    def measure(operation: Callable[[], object]) -> list[int]:
        samples: list[int] = []
        for _ in range(iterations):
            started = perf_counter_ns()
            operation()
            samples.append(perf_counter_ns() - started)
        return samples

    samples = measure(lambda: catalog.enrich_request(request))
    legacy_samples = measure(lambda: catalog.enrich_legacy_request(legacy_request))

    def report(samples: list[int]) -> dict[str, float]:
        return {
            "p50_us": statistics.median(samples) / 1_000,
            "p95_us": percentile(samples, 0.95) / 1_000,
            "max_us": max(samples) / 1_000,
        }

    legacy_report = report(legacy_samples)
    v2_report = report(samples)
    return {
        "operation": "scenario_catalog.enrich_request",
        "iterations": iterations,
        "catalog_size": len(catalog.list()),
        **v2_report,
        "legacy_task_binding": {
            "operation": "scenario_catalog.enrich_legacy_request",
            **legacy_report,
        },
        "network_calls": 0,
        "provider_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark local scenario catalog binding"
    )
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    print(json.dumps(benchmark(args.iterations), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
