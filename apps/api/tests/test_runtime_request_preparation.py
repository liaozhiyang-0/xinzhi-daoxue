from __future__ import annotations

from typing import NoReturn

import pytest
from app.contracts import (
    AgentExecutionPlan,
    AgentRequest,
    ExecutionTimeBudget,
    RouteDecision,
    RouteStatus,
)
from app.services.runtime_request_preparation import (
    RuntimeRequestPreparationService,
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
