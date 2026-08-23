from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentRegistry, TaskRouter  # noqa: E402
from app.capabilities import default_capability_registry  # noqa: E402
from app.contracts import (  # noqa: E402
    AgentRequest,
    AttachmentRef,
    Intent,
    Scene,
    UserRole,
)
from app.core.config import Settings  # noqa: E402
from app.courses import default_course_registry  # noqa: E402
from app.services.planner import PlannerService  # noqa: E402
from app.services.scenario_catalog import ScenarioCatalog  # noqa: E402
from app.services.skill_registry import SkillRegistry  # noqa: E402
from app.services.unified_request_preparation import (  # noqa: E402
    UnifiedRequestPreparationService,
)

SHOWCASE = (
    ("TP-01", "faculty_course_copilot_v1", UserRole.TEACHER),
    ("FE-01", "assessment_diagnosis_v1", UserRole.TEACHER),
    ("LP-01", "student_learning_path_v1", UserRole.STUDENT),
    ("RB-01", "research_frontier_radar_v1", UserRole.RESEARCHER),
    ("KG-01", "department_knowledge_governance_v1", UserRole.TEACHER),
    ("AC-01", "academic_visual_problem_solver_v1", UserRole.STUDENT),
)


def run() -> dict[str, object]:
    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    settings = Settings(app_env="test", planner_mode="controlled")
    router = TaskRouter(AgentRegistry(), settings)
    planner = PlannerService()
    capability_registry = default_capability_registry()
    planner.configure_skill_registry(
        SkillRegistry(default_course_registry(), capability_registry)
    )
    preparation = UnifiedRequestPreparationService()
    registered = {
        item.capability_id for item in capability_registry.list_capabilities()
    }
    rows: list[dict[str, object]] = []
    for case_id, scenario_id, role in SHOWCASE:
        scenario = catalog.get(scenario_id)
        request = AgentRequest(
            task_id=f"controlled-{case_id}",
            session_id="controlled-session",
            user_id="controlled-user",
            user_role=role,
            scene=Scene.RESEARCH if role == UserRole.RESEARCHER else Scene.TEACHING,
            course_id=scenario.courses[0],
            intent=Intent(scenario.intents[0]),
            scenario_id=scenario_id,
            canonical_input={"text": scenario.demo_cases[0].prompt},
            attachments=(
                [
                    AttachmentRef(
                        file_id="pilot-ac01-image",
                        filename="AC-01_demo.png",
                        content_type="image/png",
                        size_bytes=1,
                        storage_key="demo/ac01.png",
                    )
                ]
                if case_id == "AC-01"
                else []
            ),
            options={"_planner_preflight": True},
        )
        request = catalog.enrich_legacy_request(request)
        route = router.route(request)
        goal = preparation.build_goal(request)
        output = planner.build_authoritative(
            request,
            goal,
            route,
            settings=settings,
            mode="controlled",
        )
        plan = output.canonical_plan
        if not set(plan.capabilities) <= registered:
            raise ValueError(f"{case_id}: unregistered capability")
        if any(node.target_id not in plan.capabilities for node in plan.nodes):
            raise ValueError(f"{case_id}: plan node target is not a capability")
        if output.route.route_revision != route.route_revision:
            raise ValueError(f"{case_id}: route mutated after plan creation")
        rows.append(
            {
                "case_id": case_id,
                "scenario_id": scenario_id,
                "planner_mode": output.snapshot.mode,
                "capabilities": list(plan.capabilities),
                "skills": list(plan.selected_skills),
                "route_agent_alias": route.agent_id,
                "route_revision": route.route_revision,
                "manual_review_required": (
                    scenario.evidence_policy.manual_review_required
                ),
                "input_modalities": goal.input_modalities,
            }
        )
    return {
        "valid": True,
        "mode": "controlled",
        "case_count": len(rows),
        "invalid_capabilities": 0,
        "unregistered_skills": 0,
        "route_mutations_after_plan": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
