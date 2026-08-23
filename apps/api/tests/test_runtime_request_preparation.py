from __future__ import annotations

from types import SimpleNamespace
from typing import NoReturn

import pytest
from app.contracts import (
    AgentExecutionPlan,
    AgentRequest,
    ExecutionTimeBudget,
    IntentExecutionPlan,
    RouteDecision,
    RouteStatus,
)
from app.services.intent_plan import IntentPlanCompiler
from app.services.overall_routing import OverallRoutingOutcome
from app.services.runtime_request_preparation import (
    RuntimeRequestPreparation,
    RuntimeRequestPreparationService,
)
from app.services.task_runtime_preparation import (
    TaskRuntimePreparationService,
    _route_progress_detail,
)


class FailingRouter:
    async def route(
        self, _request: AgentRequest, _decision: RouteDecision
    ) -> NoReturn:
        raise AssertionError("resumed Runtime must not refine its route")


class FailingContextAssembly:
    async def assemble(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("resumed Runtime must not rebuild context")


class FailingPlanner:
    def build(
        self, _decision: RouteDecision, _request: AgentRequest
    ) -> NoReturn:
        raise AssertionError("resumed Runtime must reuse its execution plan")


class StaticPlanner:
    def build(
        self, _decision: RouteDecision, _request: AgentRequest
    ) -> AgentExecutionPlan:
        return _plan()


class RefiningRouter:
    def __init__(self, decision: RouteDecision) -> None:
        self.decision = decision

    async def route(
        self, _request: AgentRequest, _decision: RouteDecision
    ) -> OverallRoutingOutcome:
        return OverallRoutingOutcome(
            decision=self.decision,
            used=True,
            latency_ms=1,
            metadata={"status": "completed", "model_calls": 1},
        )


def _decision() -> RouteDecision:
    return RouteDecision(
        agent_id="GENERAL_QUESTION_V1",
        scene="dispatch",
        course_id="UNKNOWN",
        intent="general_qa",
        route_status=RouteStatus.SELECTED,
        reason="test",
        retrieval_required=False,
        provider_required=False,
    )


def _plan() -> AgentExecutionPlan:
    return AgentExecutionPlan(
        agent_id="GENERAL_QUESTION_V1",
        provider_type="local_agent",
        route_status="selected",
        use_rag=False,
        retrieval_policy_name="none",
        retrieval_mode="none",
        use_images=False,
        reranker_mode="none",
        context_budget=1_000,
        cloud_timeout_seconds=30,
        fallback_type="none",
        fallback_handler="no_fallback",
        input_mode="text",
        configured=True,
        published=True,
        debug_enabled=False,
        budget=ExecutionTimeBudget.create(cloud_timeout_seconds=30),
    )


def test_preparation_snapshot_records_route_and_plan_capabilities() -> None:
    preparation = RuntimeRequestPreparation(
        request=AgentRequest(
            task_id="request-preparation-snapshot",
            session_id="session-snapshot",
            user_id="user-snapshot",
        ),
        decision=_decision().model_copy(
            update={"availability": {"provider_available": True}}
        ),
        agent_id="GENERAL_QUESTION_V1",
        conversation_bundle=None,
        route_latency_ms=0,
        route_metadata={"status": "not_configured"},
        route_reevaluated=None,
        execution_plan=_plan().model_copy(
            update={"availability_checks": {"published": True}}
        ),
    )

    snapshot = preparation.to_snapshot()

    assert snapshot.route_capability_checks == {"provider_available": True}
    assert snapshot.execution_plan_capability_checks == {"published": True}


@pytest.mark.asyncio
async def test_resume_reuses_checkpointed_context_and_execution_plan() -> None:
    plan = _plan()
    request = AgentRequest(
        task_id="request-preparation-resume",
        session_id="session-resume",
        user_id="user-resume",
        options={
            "_routing": _decision().model_dump(mode="json"),
            "_execution_plan": plan.model_dump(mode="json"),
        },
    )
    service = RuntimeRequestPreparationService(
        FailingPlanner(),  # type: ignore[arg-type]
        FailingRouter(),  # type: ignore[arg-type]
        FailingContextAssembly(),  # type: ignore[arg-type]
    )

    prepared = await service.prepare(
        None,  # type: ignore[arg-type]
        request=request,
        decision=_decision(),
        agent_id="GENERAL_QUESTION_V1",
        session_id="session-resume",
        user_id="user-resume",
        current_message_id=None,
        course_id="UNKNOWN",
        fallback_task_family="general_qa",
        runtime_resume=True,
    )

    assert prepared.request == request
    assert prepared.execution_plan == plan
    assert prepared.conversation_bundle is None
    assert prepared.route_metadata["status"] == "restored"
    assert prepared.route_latency_ms == 0


@pytest.mark.asyncio
async def test_route_refinement_recompiles_stale_intent_plan() -> None:
    initial = _decision()
    refined = initial.model_copy(
        update={
            "agent_id": "RESEARCH_FRONTIER_BRIEF_LOCAL_V1",
            "intent": "academic_search",
            "intent_recognition": {"intent": "academic_search"},
            "route_confidence": 0.8,
        }
    )
    request = AgentRequest(
        task_id="request-preparation-route-refresh",
        session_id="session-route-refresh",
        user_id="user-route-refresh",
        options={
            "_routing": initial.model_dump(mode="json"),
            "_intent_plan": IntentPlanCompiler()
            .compile(
                AgentRequest(
                    task_id="request-preparation-route-refresh",
                    session_id="session-route-refresh",
                    user_id="user-route-refresh",
                ),
                initial,
            )
            .model_dump(mode="json"),
        },
    )
    service = RuntimeRequestPreparationService(
        StaticPlanner(),  # type: ignore[arg-type]
        RefiningRouter(refined),  # type: ignore[arg-type]
        None,
    )

    prepared = await service.prepare(
        None,  # type: ignore[arg-type]
        request=request,
        decision=initial,
        agent_id=initial.agent_id,
        session_id=request.session_id,
        user_id=request.user_id,
        current_message_id=None,
        course_id=initial.course_id,
        fallback_task_family=initial.intent,
        runtime_resume=False,
    )

    refreshed = IntentExecutionPlan.model_validate(
        prepared.request.options["_intent_plan"]
    )
    assert refreshed.nodes[0].target_id == "external_retrieval"
    assert refreshed.nodes[1].target_id == "ACADEMIC_PAPER_REVIEW_LOCAL_V1"


@pytest.mark.asyncio
async def test_planner_takeover_skips_legacy_overall_router() -> None:
    decision = _decision()
    request = AgentRequest(
        task_id="request-preparation-planner-takeover",
        session_id="session-planner-takeover",
        user_id="user-planner-takeover",
        options={
            "_planner_snapshot": {
                "mode": "takeover",
                "status": "completed",
                "planner_version": "planner-v1",
            }
        },
    )
    service = RuntimeRequestPreparationService(
        StaticPlanner(),  # type: ignore[arg-type]
        FailingRouter(),  # type: ignore[arg-type]
        None,
    )

    prepared = await service.prepare(
        None,  # type: ignore[arg-type]
        request=request,
        decision=decision,
        agent_id=decision.agent_id,
        session_id=request.session_id,
        user_id=request.user_id,
        current_message_id=None,
        course_id=decision.course_id,
        fallback_task_family=decision.intent,
        runtime_resume=False,
    )

    assert prepared.route_metadata["status"] == "planner_takeover"
    assert prepared.route_metadata["model_calls"] == 0
    assert prepared.decision == decision


@pytest.mark.asyncio
async def test_active_planner_skips_both_legacy_route_refiners() -> None:
    decision = _decision()
    request = AgentRequest(
        task_id="request-preparation-planner-active",
        session_id="session-planner-active",
        user_id="user-planner-active",
        options={
            "_planner_snapshot": {
                "mode": "active",
                "status": "completed",
                "planner_version": "planner-v1",
            }
        },
    )
    service = RuntimeRequestPreparationService(
        StaticPlanner(),  # type: ignore[arg-type]
        FailingRouter(),  # type: ignore[arg-type]
        None,
    )

    prepared = await service.prepare(
        None,  # type: ignore[arg-type]
        request=request,
        decision=decision,
        agent_id=decision.agent_id,
        session_id=request.session_id,
        user_id=request.user_id,
        current_message_id=None,
        course_id=decision.course_id,
        fallback_task_family=decision.intent,
        runtime_resume=False,
    )

    assert prepared.route_metadata["status"] == "planner_active"
    assert prepared.route_reevaluated is None


@pytest.mark.parametrize(
    ("mode", "internal_available", "expected"),
    [
        ("external_search", True, "external_retrieval"),
        ("retrieval_only", True, "local"),
        ("provider", True, "local_agent"),
        ("provider", False, "mock"),
    ],
)
def test_active_provider_uses_final_agent_definition(
    mode: str, internal_available: bool, expected: str
) -> None:
    service = TaskRuntimePreparationService.__new__(TaskRuntimePreparationService)
    service.provider = SimpleNamespace(provider_name="mock")

    definition = SimpleNamespace(mode=mode)

    assert service._active_provider(definition, internal_available) == expected


def test_route_progress_does_not_call_skipped_refinement_a_fallback() -> None:
    assert (
        _route_progress_detail(
            {
                "status": "fallback",
                "fallback_reason": "high_confidence_local_route",
            }
        )
        == "selected"
    )
    assert (
        _route_progress_detail(
            {"status": "fallback", "fallback_router": {"status": "completed"}}
        )
        == "fallback"
    )
