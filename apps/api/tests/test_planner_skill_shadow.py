from __future__ import annotations

import pytest
from app.capabilities import default_capability_registry
from app.contracts import AgentRequest, RouteDecision, RouteStatus
from app.core.config import Settings
from app.courses import default_course_registry
from app.services.intent_plan import IntentPlanCompiler
from app.services.planner import PlannerService
from app.services.skill_registry import SkillRegistry


def _services() -> PlannerService:
    return PlannerService(
        skill_registry=SkillRegistry(
            default_course_registry(), default_capability_registry()
        )
    )


def _case(
    *,
    task_id: str,
    course: str,
    objective: str,
    problem_type: str,
    capabilities: list[str] | None = None,
    selected_skills: list[str] | None = None,
    options: dict[str, object] | None = None,
) -> tuple[AgentRequest, RouteDecision]:
    request = AgentRequest(
        task_id=task_id,
        session_id=f"session-{task_id}",
        user_id=f"user-{task_id}",
        course_id=course,
        canonical_input={"text": objective},
        options=options or {},
    )
    route = RouteDecision(
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        scene="academic",
        course_id=course,
        intent="solve_problem",
        route_status=RouteStatus.SELECTED,
        reason="skill shadow fixture",
        retrieval_required=False,
        provider_required=False,
        capabilities=capabilities or [],
        selected_skills=selected_skills or [],
        intent_recognition={"problem_type": problem_type},
    )
    return request, route


@pytest.mark.parametrize(
    ("request_route", "expected"),
    [
        (
            _case(
                task_id="ct-shadow",
                course="CT",
                objective="节点电压法求节点电压",
                problem_type="node_voltage",
                capabilities=["circuit_analysis"],
                selected_skills=["CT.KCL"],
            ),
            ["CT.NODAL"],
        ),
        (
            _case(
                task_id="knowledge-shadow",
                course="KNOWLEDGE",
                objective="改写一个有依据的知识问题",
                problem_type="knowledge_qa",
                options={
                    "available_workers": ["KnowledgeQAService"],
                    "evidence_state": {"query_text": True},
                },
            ),
            ["KNOWLEDGE.QUERY_REWRITE"],
        ),
        (
            _case(
                task_id="teaching-shadow",
                course="CT",
                objective="求一阶电路换路后的初值",
                problem_type="first_order",
                capabilities=["circuit_analysis"],
                selected_skills=["CT.KCL", "CT.KVL"],
            ),
            ["CT.FIRST_ORDER_INITIAL"],
        ),
        (
            _case(
                task_id="research-shadow",
                course="RESEARCH",
                objective="规划学术检索问题",
                problem_type="academic_search",
                options={
                    "available_workers": ["AcademicSearchPlannerService"],
                    "evidence_state": {"query_scope": True},
                },
            ),
            ["RESEARCH.QUERY_PLANNING"],
        ),
        (
            _case(
                task_id="general-shadow",
                course="UNKNOWN",
                objective="帮我安排一个学习任务",
                problem_type="general",
            ),
            [],
        ),
    ],
)
def test_planner_shadow_records_skill_selection_without_runtime_execution(
    request_route: tuple[AgentRequest, RouteDecision], expected: list[str]
) -> None:
    request, route = request_route
    output = _services().build(
        request,
        route,
        settings=Settings(planner_shadow_enabled=True),
        intent_plan=IntentPlanCompiler().compile(request, route),
    )

    assert output.canonical_plan.selected_skills == expected
    assert output.snapshot.planner_skills == expected
    assert output.snapshot.skill_selection_status in {"selected", "empty"}
    if expected:
        assert output.snapshot.model_dump(mode="json")["planner_skill_selection"]
    else:
        assert output.snapshot.model_dump(mode="json")["planner_skill_selection"] == []
    assert all(node.node_type != "skill" for node in output.canonical_plan.nodes)


def test_planner_shadow_keeps_rejection_reason_for_missing_research_dependencies(
) -> None:
    request, route = _case(
        task_id="research-rejected-shadow",
        course="RESEARCH",
        objective="评审研究证据",
        problem_type="evidence_review",
        options={"evidence_state": {"source_refs": True}},
    )

    output = _services().build(
        request,
        route,
        settings=Settings(planner_shadow_enabled=True),
    )

    assert output.canonical_plan.selected_skills == []
    assert output.snapshot.skill_selection_status == "rejected"
    assert "prerequisite_missing" in output.snapshot.skill_rejection_reasons
    assert "worker_dependency_unavailable" in output.snapshot.skill_rejection_reasons
