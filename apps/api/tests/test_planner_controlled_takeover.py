from pathlib import Path

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.capabilities import default_capability_registry
from app.contracts import AgentRequest, Intent, Scene, UserRole
from app.core.config import Settings
from app.courses import default_course_registry
from app.services.planner import PlannerService
from app.services.scenario_catalog import ScenarioCatalog
from app.services.skill_registry import SkillRegistry
from app.services.unified_request_preparation import (
    UnifiedRequestPreparationService,
)

SHOWCASE_SCENARIOS = (
    ("TP-01", "faculty_course_copilot_v1", UserRole.TEACHER),
    ("FE-01", "assessment_diagnosis_v1", UserRole.TEACHER),
    ("LP-01", "student_learning_path_v1", UserRole.STUDENT),
    ("RB-01", "research_frontier_radar_v1", UserRole.RESEARCHER),
    ("KG-01", "department_knowledge_governance_v1", UserRole.TEACHER),
    ("AC-01", "academic_visual_problem_solver_v1", UserRole.STUDENT),
)


@pytest.mark.parametrize("case_id,scenario_id,role", SHOWCASE_SCENARIOS)
def test_controlled_planner_owns_six_showcase_plans(
    case_id: str, scenario_id: str, role: UserRole
) -> None:
    catalog = ScenarioCatalog(Path("config/scenarios.yaml"))
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
        options={"_planner_preflight": True},
    )
    request = catalog.enrich_legacy_request(request)
    settings = Settings(app_env="test", planner_mode="controlled")
    route = TaskRouter(AgentRegistry(), settings).route(request)
    goal = UnifiedRequestPreparationService().build_goal(request)
    planner = PlannerService()
    planner.configure_skill_registry(
        SkillRegistry(default_course_registry(), default_capability_registry())
    )

    output = planner.build_authoritative(
        request,
        goal,
        route,
        settings=settings,
        mode="controlled",
    )

    registered = {
        item.capability_id for item in default_capability_registry().list_capabilities()
    }
    assert output.snapshot.mode == "controlled"
    assert output.canonical_plan.source == "planner_authoritative"
    assert set(output.canonical_plan.capabilities) <= registered
    assert output.canonical_plan.capability_bindings
    assert all(
        item.capability_id in output.canonical_plan.capabilities
        for item in output.canonical_plan.capability_bindings
    )
    assert output.route.route_revision == route.route_revision
    assert (
        output.canonical_plan.nodes[0].target_id
        in output.canonical_plan.capabilities
    )
