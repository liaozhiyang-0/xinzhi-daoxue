from __future__ import annotations

from app.contracts import AgentRequest, Intent, RouteDecision, RouteStatus
from app.core.config import Settings
from app.services.planner import PlannerService
from app.services.task_runtime_preparation import TaskRuntimePreparationService


def _request() -> AgentRequest:
    return AgentRequest(
        task_id="planner-canary-task",
        session_id="planner-canary-session",
        user_id="planner-canary-user",
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "canary request"},
        options={
            "_routing": {"agent_id": "GENERAL_QUESTION_V1"},
        },
    )


def _route() -> RouteDecision:
    return RouteDecision(
        agent_id="GENERAL_QUESTION_V1",
        scene="dispatch",
        course_id="UNKNOWN",
        intent="general_qa",
        route_status=RouteStatus.SELECTED,
        reason="canary test",
        retrieval_required=False,
        provider_required=False,
    )


def test_takeover_is_fail_closed_and_allowlisted() -> None:
    request = _request()
    disabled = Settings(planner_takeover_enabled=True)
    assert PlannerService.takeover_allowed(request, disabled) is False

    enabled = Settings(
        planner_takeover_enabled=True,
        planner_canary_agent_ids="GENERAL_QUESTION_V1",
    )
    assert PlannerService.takeover_allowed(request, enabled) is True

    denied = Settings(
        planner_takeover_enabled=True,
        planner_canary_agent_ids="ACADEMIC_PROBLEM_SOLVER",
    )
    assert PlannerService.takeover_allowed(request, denied) is False


def test_takeover_marks_route_and_canonical_plan_for_runtime_adapter() -> None:
    request = _request()
    settings = Settings(
        planner_takeover_enabled=True,
        planner_canary_agent_ids="GENERAL_QUESTION_V1",
    )
    planner = PlannerService()
    output = planner.build(
        request,
        _route(),
        settings=settings,
        mode="takeover",
    )
    assert output.snapshot.mode == "takeover"
    takeover_route = planner.takeover_route(_route())
    assert takeover_route.route_source == "planner_takeover"
    assert takeover_route.route_revision == 1
    assert "planner_takeover" in takeover_route.reason_codes

    takeover_request = request.model_copy(
        update={
            "options": {
                "_planner_snapshot": output.snapshot.model_dump(mode="json")
            }
        }
    )
    runtime_plan = TaskRuntimePreparationService._planner_runtime_plan(
        takeover_request
    )
    assert runtime_plan is not None
    assert runtime_plan.plan_id == output.canonical_plan.plan_id
    assert runtime_plan.nodes[0].target_id == "GENERAL_QUESTION_V1"
