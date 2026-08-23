from pathlib import Path

from app.agents import AgentRegistry, TaskRouter
from app.capabilities import default_capability_registry
from app.contracts import AgentRequest, Intent, Scene, UserRole
from app.core.config import Settings
from app.courses import default_course_registry
from app.runtime import RuntimeHandlerDescriptor, RuntimeHandlerRegistry
from app.services.planner import PlannerService
from app.services.scenario_catalog import ScenarioCatalog
from app.services.skill_binding import SkillBindingService
from app.services.skill_registry import SkillRegistry
from app.services.unified_request_preparation import (
    UnifiedRequestPreparationService,
)


def test_authoritative_planner_owns_canonical_capability_without_route_mutation(
) -> None:
    catalog = ScenarioCatalog(Path("config/scenarios.yaml"))
    scenario = catalog.get("academic_visual_problem_solver_v1")
    request = AgentRequest(
        session_id="session-planner",
        user_id="user-planner",
        user_role=UserRole.STUDENT,
        scene=Scene.SOLVING,
        course_id="AE",
        intent=Intent.SOLVE_PROBLEM,
        scenario_id=scenario.id,
        canonical_input={"text": scenario.demo_cases[0].prompt},
    )
    request = catalog.enrich_legacy_request(request)
    settings = Settings(app_env="test")
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
        mode="active",
    )

    assert output.snapshot.mode == "active"
    assert output.canonical_plan.source == "planner_authoritative"
    assert output.canonical_plan.nodes[0].target_id == "academic.solve"
    assert output.canonical_plan.nodes[0].target_id != route.agent_id
    assert output.route.route_revision == route.route_revision
    assert output.canonical_plan.capability_bindings[0].handler_id == route.agent_id


def test_authoritative_planner_binds_an_approved_domain_skill_to_runtime() -> None:
    catalog = ScenarioCatalog(Path("config/scenarios.yaml"))
    scenario = catalog.get("academic_visual_problem_solver_v1")
    request = AgentRequest(
        task_id="planner-skill-binding",
        session_id="session-planner-skill",
        user_id="user-planner-skill",
        user_role=UserRole.STUDENT,
        scene=Scene.SOLVING,
        course_id="CT",
        intent=Intent.SOLVE_PROBLEM,
        scenario_id=scenario.id,
        canonical_input={"text": scenario.demo_cases[0].prompt},
        options={"evidence_state": {"image_observation": True}},
    )
    request = catalog.enrich_legacy_request(request)
    settings = Settings(app_env="test", planner_mode="active")
    route = TaskRouter(AgentRegistry(), settings).route(request)
    goal = UnifiedRequestPreparationService().build_goal(request)
    registry = SkillRegistry(
        default_course_registry(), default_capability_registry()
    )
    handlers = RuntimeHandlerRegistry()
    handlers.register(
        RuntimeHandlerDescriptor(
            handler_id="subagent.ACADEMIC_PROBLEM_SOLVER",
            kind="subagent",
        ),
        lambda run, node: None,
    )
    planner = PlannerService(skill_registry=registry)
    planner.configure_skill_binding_service(
        SkillBindingService(
            registry,
            handlers,
            available_workers=["AcademicProblemSolver"],
        )
    )

    output = planner.build_authoritative(
        request,
        goal,
        route,
        settings=settings,
        mode="active",
    )

    assert output.canonical_plan.selected_skills == [
        "AE.CIRCUIT_IMAGE_PARSE"
    ]
    assert output.canonical_plan.skill_bindings[0].handler_id == (
        "subagent.ACADEMIC_PROBLEM_SOLVER"
    )
    assert output.canonical_plan.nodes[0].node_type == "skill"
    assert output.canonical_plan.nodes[0].target_id == "AE.CIRCUIT_IMAGE_PARSE"
