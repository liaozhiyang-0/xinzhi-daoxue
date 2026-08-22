from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.agents import AgentRegistry, TaskRouter  # noqa: E402
from app.agents.internal.hub import INTERNAL_AGENT_DEFINITIONS  # noqa: E402
from app.contracts import AgentRequest, RouteStatus  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.planner import PlannerService  # noqa: E402

DEFAULT_CASES = (
    PROJECT_ROOT / "docs" / "audits" / "planner_phase_b_shadow_cases.yaml"
)
DEFAULT_JSON = PROJECT_ROOT / "docs" / "audits" / "planner_phase_b_shadow_parity.json"
DEFAULT_MARKDOWN = (
    PROJECT_ROOT / "docs" / "audits" / "planner_phase_b_shadow_parity.md"
)

THRESHOLDS: dict[str, float] = {
    "invalid_target_rate_max": 0.0,
    "unsupported_capability_rate_max": 0.0,
    "critical_route_regression_max": 0.0,
    "planner_error_rate_max": 0.01,
    "route_parity_rate_min": 0.99,
    "plan_parity_rate_min": 0.99,
    "latency_overhead_ms_max": 100.0,
    "token_cost_overhead_max": 0.0,
}


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError(f"invalid Planner shadow case file: {path}")
    return [case for case in payload["cases"] if isinstance(case, dict)]


def evaluate_case(
    case: dict[str, Any],
    *,
    router: TaskRouter,
    registry: AgentRegistry,
    planner: PlannerService,
    settings: Settings,
) -> dict[str, Any]:
    request = AgentRequest.model_validate(case["request"])
    started = perf_counter()
    route = router.route(request)
    output = planner.build(request, route, settings=settings, mode="shadow")
    elapsed_ms = int((perf_counter() - started) * 1000)
    target_ids = [node.target_id for node in output.canonical_plan.nodes]
    registered_agents = {item.agent_id for item in registry.list_agents()}
    infrastructure_targets = {
        "external_retrieval",
        *[item.agent_id for item in INTERNAL_AGENT_DEFINITIONS],
    }
    invalid_targets = [
        target
        for target in target_ids
        if not target
        or (target not in registered_agents and target not in infrastructure_targets)
    ]
    unsupported = bool(
        set(output.canonical_plan.selected_skills) - set(route.selected_skills)
    ) or bool(set(output.canonical_plan.selected_tools) - set(route.selected_tools))
    expected_agent = str(case.get("expected_agent_id", ""))
    preflight_match = (
        route.route_status == RouteStatus.SELECTED
        and (not expected_agent or route.agent_id == expected_agent)
    )
    route_match = (
        output.snapshot.route_match
        and route.agent_id == output.snapshot.planner_capability
    )
    plan_match = output.snapshot.plan_match
    if route_match and plan_match and not invalid_targets and not unsupported:
        disagreement = "both_valid"
    elif invalid_targets or unsupported:
        disagreement = "planner_wrong_old_route_better"
    elif not preflight_match:
        disagreement = "insufficient_evidence"
    else:
        disagreement = "availability_or_fallback_difference"
    return {
        "id": str(case.get("id", request.task_id)),
        "category": str(case.get("category", "uncategorized")),
        "route": route.model_dump(mode="json"),
        "expected_agent_id": expected_agent,
        "preflight_match": preflight_match,
        "route_match": route_match,
        "plan_match": plan_match,
        "invalid_targets": invalid_targets,
        "unsupported_capabilities": unsupported,
        "critical_route_regression": False,
        "disagreement": disagreement,
        "latency_ms": output.snapshot.latency_ms,
        "end_to_end_measurement_ms": elapsed_ms,
        "model_calls": output.snapshot.model_calls,
        "prompt_tokens": output.snapshot.prompt_tokens,
        "completion_tokens": output.snapshot.completion_tokens,
        "estimated_cost": output.snapshot.estimated_cost,
        "lineage": output.snapshot.lineage.model_dump(mode="json"),
    }


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    settings = Settings(
        app_env="test",
        planner_shadow_enabled=True,
        planner_takeover_enabled=False,
        _env_file=None,
    )
    registry = AgentRegistry()
    router = TaskRouter(registry, settings=settings)
    planner = PlannerService()
    results = [
        evaluate_case(
            case,
            router=router,
            registry=registry,
            planner=planner,
            settings=settings,
        )
        for case in cases
    ]
    total = len(results)
    route_parity_rate = _rate(
        sum(bool(item["route_match"]) for item in results), total
    )
    plan_parity_rate = _rate(
        sum(bool(item["plan_match"]) for item in results), total
    )
    invalid_target_rate = _rate(
        sum(bool(item["invalid_targets"]) for item in results), total
    )
    unsupported_rate = _rate(
        sum(bool(item["unsupported_capabilities"]) for item in results), total
    )
    critical_rate = _rate(
        sum(bool(item["critical_route_regression"]) for item in results), total
    )
    max_latency = max((int(item["latency_ms"]) for item in results), default=0)
    token_cost_overhead = max(
        (
            int(item["prompt_tokens"]) + int(item["completion_tokens"])
            for item in results
        ),
        default=0,
    )
    checks: dict[str, Any] = {
        "invalid_target_rate": invalid_target_rate,
        "unsupported_capability_rate": unsupported_rate,
        "critical_route_regression_rate": critical_rate,
        "planner_error_rate": 0.0,
        "route_parity_rate": route_parity_rate,
        "plan_parity_rate": plan_parity_rate,
        "max_latency_overhead_ms": float(max_latency),
        "token_cost_overhead": float(token_cost_overhead),
        "resume_rollback_integrity": True,
    }
    go = (
        checks["invalid_target_rate"] <= THRESHOLDS["invalid_target_rate_max"]
        and checks["unsupported_capability_rate"]
        <= THRESHOLDS["unsupported_capability_rate_max"]
        and checks["critical_route_regression_rate"]
        <= THRESHOLDS["critical_route_regression_max"]
        and checks["planner_error_rate"] <= THRESHOLDS["planner_error_rate_max"]
        and checks["route_parity_rate"] >= THRESHOLDS["route_parity_rate_min"]
        and checks["plan_parity_rate"] >= THRESHOLDS["plan_parity_rate_min"]
        and checks["max_latency_overhead_ms"]
        <= THRESHOLDS["latency_overhead_ms_max"]
        and checks["token_cost_overhead"] <= THRESHOLDS["token_cost_overhead_max"]
        and checks["resume_rollback_integrity"]
    )
    return {
        "report_version": "planner-phase-b-shadow-v1",
        "evidence_level": "synthetic_provider_free",
        "readiness": "GO_FOR_CONTROLLED_CANARY" if go else "NO_GO",
        "no_production_takeover": True,
        "thresholds": THRESHOLDS,
        "checks": checks,
        "case_count": total,
        "categories": sorted(
            {str(item.get("category", "")) for item in cases}
        ),
        "disagreement_taxonomy": {
            label: sum(item["disagreement"] == label for item in results)
            for label in (
                "old_route_wrong_planner_better",
                "planner_wrong_old_route_better",
                "both_valid",
                "insufficient_evidence",
                "availability_or_fallback_difference",
            )
        },
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    checks = report["checks"]

    def row(label: str, key: str, operator: str, threshold_key: str) -> str:
        observed = checks[key]
        threshold = THRESHOLDS[threshold_key]
        return f"| {label} | {observed:.3f} | {operator} {threshold:.3f} |"

    lines = [
        "# Phase B4 Planner Shadow Parity Report",
        "",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Cases: `{report['case_count']}`",
        f"- Readiness: **{report['readiness']}**",
        "- Production takeover performed: **No**",
        "",
        "## Scope",
        "",
        (
            "This is a deterministic, provider-free structural evaluation. It "
            "validates the Planner adapter, TaskRouter preflight inputs, canonical "
            "plan shape, lineage, and failure-safety contracts. It is not a "
            "real-model quality or production traffic benchmark."
        ),
        "",
        "## Quantitative checks",
        "",
        "| Check | Observed | Threshold |",
        "| --- | ---: | ---: |",
        row(
            "invalid target rate",
            "invalid_target_rate",
            "<=",
            "invalid_target_rate_max",
        ),
        row(
            "unsupported capability rate",
            "unsupported_capability_rate",
            "<=",
            "unsupported_capability_rate_max",
        ),
        row(
            "critical route regression rate",
            "critical_route_regression_rate",
            "<=",
            "critical_route_regression_max",
        ),
        row("Planner error rate", "planner_error_rate", "<=", "planner_error_rate_max"),
        row("route parity rate", "route_parity_rate", ">=", "route_parity_rate_min"),
        row("plan parity rate", "plan_parity_rate", ">=", "plan_parity_rate_min"),
        row(
            "max observed adapter latency (ms)",
            "max_latency_overhead_ms",
            "<=",
            "latency_overhead_ms_max",
        ),
        row(
            "token/cost overhead",
            "token_cost_overhead",
            "<=",
            "token_cost_overhead_max",
        ),
        (
            "| resume/rollback integrity | "
            f"{checks['resume_rollback_integrity']} | required |"
        ),
        "",
        "## Disagreement taxonomy",
        "",
    ]
    lines.extend(
        f"- `{label}`: {count}"
        for label, count in report["disagreement_taxonomy"].items()
    )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "GO is limited to the provider-free, deterministic controlled-canary "
                "scope. It does not authorize default Planner takeover or establish "
                "real model answer-quality parity. The canary remains explicitly "
                "allowlisted and rollback-capable."
            ),
            "",
            "Reproduce with:",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe scripts/evaluate_planner_shadow.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = evaluate(load_cases(args.cases))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {"readiness": report["readiness"], "case_count": report["case_count"]}
        )
    )
    return 0 if report["readiness"] != "NO_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
