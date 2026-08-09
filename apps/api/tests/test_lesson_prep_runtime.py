from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

import pytest
from app.contracts import AgentRequest, AgentResult, AgentResultStatus, Intent
from app.runtime import (
    AgentRun,
    DecisionAction,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.lesson_prep_runtime import LessonPrepRuntimeService


def make_result(
    *,
    status: AgentResultStatus = AgentResultStatus.COMPLETED,
    answer: str = "## Lesson plan",
    business_data: dict[str, Any] | None = None,
) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id=LessonPrepRuntimeService.agent_id,
        provider="local_agent",
        answer=answer,
        business_data=(
            business_data
            if business_data is not None
            else {
                "learning_objectives": ["Explain the concept"],
                "lesson_flow": ["Introduce", "Practice"],
                "activities": ["Guided practice"],
                "formative_assessment": ["Exit ticket"],
            }
        ),
    )


def make_request(task_id: str = "task-lesson-runtime") -> AgentRequest:
    return AgentRequest(
        task_id=task_id,
        session_id="session-1",
        user_id="user-1",
        intent=Intent.LESSON_PREP,
        canonical_input={"text": "Prepare a lesson"},
        options={"lesson_prep_runtime": {"execute": True}},
    )


class FakeLessonAgents:
    """Deterministic provider-free Agent boundary."""

    def __init__(self, results: Iterable[AgentResult]) -> None:
        self.results = list(results)
        if not self.results:
            raise ValueError("at least one fake result is required")
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del request, context
        assert agent_id == LessonPrepRuntimeService.agent_id
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result.model_copy(update={"agent_id": agent_id})


def make_run(
    service: LessonPrepRuntimeService, request: AgentRequest
) -> AgentRun:
    return AgentRun(
        run_id=f"{request.task_id}-run",
        task_id=request.task_id,
        goal="Prepare a lesson",
        plan=service.build_plan(request),
    )


def test_lesson_prep_runtime_verifies_business_contract_after_replan() -> None:
    fake = FakeLessonAgents(
        [
            make_result(status=AgentResultStatus.FAILED, answer=""),
            make_result(),
        ]
    )
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = make_run(service, request)

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["lesson.execute.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    assert run.nodes["lesson.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )


def test_lesson_prep_business_contract_is_fail_closed() -> None:
    service = LessonPrepRuntimeService(object(), enabled=True)  # type: ignore[arg-type]

    assert service._is_valid_result(make_result())
    assert not service._is_valid_result(
        make_result(
            business_data={
                "learning_objectives": ["Explain the concept"],
                "lesson_flow": ["Introduce", "Practice"],
                "activities": ["Guided practice"],
            }
        )
    )
    assert not service._is_valid_result(
        make_result(
            business_data={
                "learning_objectives": ["TBD"],
                "lesson_flow": ["Introduce", "Practice"],
                "activities": ["Guided practice"],
                "formative_assessment": ["Exit ticket"],
            }
        )
    )


def test_low_quality_plan_waits_for_approval_and_resume_reuses_execution() -> None:
    fake = FakeLessonAgents(
        [
            make_result(
                business_data={
                    "learning_objectives": ["Explain the concept"],
                    "lesson_flow": ["Introduce"],
                    "activities": ["Guided practice"],
                    "formative_assessment": ["Exit ticket"],
                }
            )
        ]
    )
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request("task-lesson-approval")
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended) as suspended:
        asyncio.run(service.run(request, run))

    assert suspended.value.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.last_decision is not None
    assert run.last_decision.action == DecisionAction.REQUEST_APPROVAL
    assert run.last_decision.approval_scope == service.approval_scope
    assert run.nodes[service.execute_node_id].attempt == 1
    assert run.nodes[service.verify_node_id].status == RuntimeNodeStatus.PARTIAL
    assert fake.calls == 1

    run.control_data["approved"] = True
    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert fake.calls == 1
    assert run.nodes[service.execute_node_id].attempt == 1
    assert run.nodes[service.verify_node_id].attempt == 1


def test_lesson_prep_checkpoint_recovery_reuses_result_without_provider_call() -> None:
    fake = FakeLessonAgents(
        [
            make_result(
                business_data={
                    "learning_objectives": ["Explain the concept"],
                    "lesson_flow": ["Introduce"],
                    "activities": ["Guided practice"],
                    "formative_assessment": ["Exit ticket"],
                }
            )
        ]
    )
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request("task-lesson-checkpoint")
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended):
        asyncio.run(service.run(request, run))
    recovered = AgentRun.model_validate(run.model_dump(mode="json"))
    recovered.control_data["approved"] = True

    result = asyncio.run(service.run(request, recovered))

    assert result.business_data["lesson_flow"] == ["Introduce"]
    assert recovered.status == RuntimeRunStatus.COMPLETED
    assert fake.calls == 1
    assert recovered.nodes[service.execute_node_id].observation is not None


def test_answer_failure_replans_within_runtime_iteration_budget() -> None:
    fake = FakeLessonAgents(
        [make_result(status=AgentResultStatus.FAILED, answer="")]
    )
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request("task-lesson-answer-budget")
    run = make_run(service, request)
    run.budget.max_iterations = 2

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.FAILED
    assert run.status == RuntimeRunStatus.FAILED
    assert run.iteration == 1
    assert fake.calls == 2
    assert run.last_decision is not None
    assert run.last_decision.reason_codes == ["lesson_prep_execution_failed"]


def test_verify_failure_replans_then_succeeds_without_refetching() -> None:
    fake = FakeLessonAgents(
        [
            make_result(
                business_data={
                    "learning_objectives": ["Explain the concept"],
                    "lesson_flow": ["Introduce", "Practice"],
                    "activities": ["Guided practice"],
                }
            ),
            make_result(),
        ]
    )
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request("task-lesson-verify-replan")
    run = make_run(service, request)

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["lesson.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )


def test_invalid_lesson_plan_never_masquerades_as_completed_after_budget() -> None:
    fake = FakeLessonAgents(
        [
            make_result(
                business_data={
                    "learning_objectives": ["Explain the concept"],
                    "lesson_flow": ["Introduce", "Practice"],
                    "activities": ["Guided practice"],
                }
            )
        ]
    )
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request("task-lesson-failed-closed")
    run = make_run(service, request)
    run.budget.max_iterations = 1

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.FAILED
    assert run.status == RuntimeRunStatus.FAILED
    assert run.last_decision is not None
    assert run.last_decision.action == DecisionAction.FAIL
    assert "lesson_prep_runtime_failed_closed" in result.warnings
