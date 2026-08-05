from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import (  # type: ignore[import-untyped]  # noqa: E402
    AgentRegistry,
    TaskRouter,
)
from app.contracts import (  # type: ignore[import-untyped]  # noqa: E402
    AgentRequest,
    Intent,
    Scene,
    UserRole,
)
from app.core.config import Settings  # type: ignore[import-untyped]  # noqa: E402
from app.evaluation.loader import (  # type: ignore[import-untyped]  # noqa: E402
    EvaluationCaseLoader,
)
from app.services.scenario_catalog import (  # type: ignore[import-untyped]  # noqa: E402
    ScenarioCatalog,
)
from app.services.scenario_preflight import (  # type: ignore[import-untyped]  # noqa: E402
    ScenarioPreflightService,
)


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def run() -> dict[str, object]:
    cases = EvaluationCaseLoader(
        ROOT / "evaluation" / "cases" / "commercial_scenarios"
    ).load_all()
    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    registry = AgentRegistry()
    settings = Settings(app_env="test")
    router = TaskRouter(registry, settings)
    preflight = ScenarioPreflightService()
    timings: list[int] = []
    rows: list[dict[str, object]] = []

    for case in cases:
        scenario_id = str(case.task_options["scenario_id"])
        role = UserRole(str(case.task_options.get("user_role", "student")))
        request = AgentRequest(
            session_id=f"preflight-{case.case_id}",
            user_id="commercial-preflight",
            user_role=role,
            scene=Scene.RESEARCH if role == UserRole.RESEARCHER else Scene.TEACHING,
            course_id=case.course,
            intent=Intent(case.intent),
            scenario_id=scenario_id,
            canonical_input={"text": case.message},
            options={"input_type": case.input_type},
        )
        started = perf_counter_ns()
        bound = catalog.enrich_legacy_request(request)
        decision = router.route(bound)
        elapsed_us = (perf_counter_ns() - started) / 1_000
        timings.append(int(elapsed_us * 1_000))
        scenario = catalog.get(scenario_id)
        readiness = preflight.check(
            scenario,
            registry=registry,
            settings=settings,
        )
        rows.append(
            {
                "case_id": case.case_id,
                "scenario_id": scenario_id,
                "expected_agent": case.expected_agent,
                "routed_agent": decision.agent_id,
                "primary_agent_match": decision.agent_id == case.expected_agent,
                "route_passed": (
                    decision.agent_id == case.expected_agent
                    or decision.original_agent_id == case.expected_agent
                ),
                "fallback_used": decision.fallback_used,
                "route_status": decision.route_status.value,
                "route_source": decision.route_source,
                "elapsed_us": elapsed_us,
                "demo_ready": readiness.demo_ready,
                "production_ready": readiness.production_ready,
                "blockers": readiness.blockers,
            }
        )

    passed = sum(bool(row["route_passed"]) for row in rows)
    return {
        "valid": passed == len(rows),
        "case_count": len(rows),
        "route_passed_count": passed,
        "p50_us": percentile(timings, 0.50) / 1_000,
        "p95_us": percentile(timings, 0.95) / 1_000,
        "network_calls": 0,
        "provider_calls": 0,
        "cases": rows,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
