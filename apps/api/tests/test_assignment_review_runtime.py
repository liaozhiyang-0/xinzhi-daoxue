from __future__ import annotations

import asyncio
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
from app.services.assignment_review_runtime import AssignmentReviewRuntimeService


class FakeAssignmentAgents:
    """Deterministic local execution fake; it never reaches a Provider."""

    def __init__(self, results: list[AgentResult]) -> None:
        self.results = results
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del request, context
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result.model_copy(update={"agent_id": agent_id})


def make_result(
    *,
    status: AgentResultStatus = AgentResultStatus.COMPLETED,
    answer: str = "initial review",
    business_data: dict[str, Any] | None = None,
) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id=AssignmentReviewRuntimeService.agent_id,
        provider="local_agent",
        answer=answer,
        business_data=(
            business_data
            if business_data is not None
            else {
                "correctness": "mostly_correct",
                "correct_parts": ["part one"],
                "errors": ["part two needs more detail"],
                "teacher_feedback": "Please add the missing analysis.",
                "review_required": False,
            }
        ),
    )


def make_request(task_id: str = "task-assignment-runtime") -> AgentRequest:
    return AgentRequest(
        task_id=task_id,
        session_id="session-1",
        user_id="user-1",
        intent=Intent.ASSIGNMENT_REVIEW,
        canonical_input={"text": "review this assignment"},
        options={"assignment_review_runtime": {"execute": True}},
    )


def make_run(
    service: AssignmentReviewRuntimeService, request: AgentRequest
) -> AgentRun:
    return AgentRun(
        run_id=f"{request.task_id}-run",
        task_id=request.task_id,
        goal="review this assignment",
        plan=service.build_plan(request),
    )


def review_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "correctness": "mostly_correct",
        "correct_parts": ["part one"],
        "errors": [],
        "teacher_feedback": "The review is ready for teacher approval.",
        "review_required": False,
    }
    data.update(overrides)
    return data


def test_assignment_review_replans_then_waits_for_quality_approval() -> None:
    fake = FakeAssignmentAgents(
        [
            make_result(status=AgentResultStatus.FAILED, answer=""),
            make_result(business_data=review_data(review_required=True)),
        ]
    )
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request()
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended) as suspended:
        asyncio.run(service.run(request, run))

    assert suspended.value.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.last_decision is not None
    assert run.last_decision.action == DecisionAction.REQUEST_APPROVAL
    assert run.last_decision.approval_scope == service.approval_scope
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["assignment.execute.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    assert run.nodes["assignment.verify.replan.1"].status == (
        RuntimeNodeStatus.PARTIAL
    )


def test_assignment_review_approval_resume_does_not_repeat_business_execution() -> None:
    fake = FakeAssignmentAgents(
        [make_result(business_data=review_data(review_required=True))]
    )
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request("task-assignment-approval-resume")
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended):
        asyncio.run(service.run(request, run))
    run.control_data["approved"] = True

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert fake.calls == 1
    assert run.control_data[service.approval_control_key] is True
    assert run.nodes[service.execute_node_id].attempt == 1
    assert run.nodes[service.verify_node_id].attempt == 1


@pytest.mark.parametrize("status_key", ["verification_status", "quality_status"])
def test_assignment_review_partial_or_degraded_validation_waits_for_approval(
    status_key: str,
) -> None:
    fake = FakeAssignmentAgents(
        [make_result(business_data=review_data(**{status_key: "partial"}))]
    )
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request(f"task-assignment-{status_key}")
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended) as suspended:
        asyncio.run(service.run(request, run))

    assert suspended.value.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert fake.calls == 1


def test_assignment_review_returns_evidence_incomplete_diagnosis_without_blocking(
) -> None:
    fake = FakeAssignmentAgents(
        [
            make_result(
                business_data=review_data(
                    review_required=True,
                    evidence_status="insufficient",
                    missing_information=["题目标准答案未提供"],
                )
            )
        ]
    )
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request("task-assignment-preliminary-evidence")
    run = make_run(service, request)

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert result.business_data["review_required"] is True
    assert fake.calls == 1


def test_assignment_review_checkpoint_recovery_preserves_approval_and_effects() -> None:
    fake = FakeAssignmentAgents(
        [make_result(business_data=review_data(review_required=True))]
    )
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request("task-assignment-checkpoint-recovery")
    run = make_run(service, request)
    checkpoints: list[RuntimeRunStatus] = []

    def checkpoint(current: AgentRun) -> None:
        checkpoints.append(current.status)

    with pytest.raises(RuntimeRunSuspended):
        asyncio.run(service.run(request, run, checkpoint_hook=checkpoint))
    recovered = AgentRun.model_validate(run.model_dump(mode="json"))
    recovered.control_data["approved"] = True

    result = asyncio.run(service.run(request, recovered, checkpoint_hook=checkpoint))

    assert result.status == AgentResultStatus.COMPLETED
    assert recovered.status == RuntimeRunStatus.COMPLETED
    assert RuntimeRunStatus.WAITING_APPROVAL in checkpoints
    assert fake.calls == 1
    assert recovered.nodes[service.execute_node_id].observation is not None
    assert recovered.nodes[service.verify_node_id].observation is not None


def test_assignment_review_answer_failure_replans_with_a_hard_iteration_bound() -> None:
    fake = FakeAssignmentAgents(
        [make_result(status=AgentResultStatus.FAILED, answer="")]
    )
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request("task-assignment-bounded-replan")
    run = make_run(service, request)
    run.budget.max_iterations = 2

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.FAILED
    assert run.status == RuntimeRunStatus.FAILED
    assert run.iteration == 1
    assert fake.calls == 2
    assert run.last_decision is not None
    assert run.last_decision.reason_codes == ["assignment_review_execution_failed"]


def test_assignment_review_verify_failure_never_masquerades_as_completed() -> None:
    fake = FakeAssignmentAgents([make_result(business_data={})])
    service = AssignmentReviewRuntimeService(fake, enabled=True)
    request = make_request("task-assignment-no-fake-completed")
    run = make_run(service, request)
    run.budget.max_iterations = 1

    with pytest.raises(RuntimeError, match="runtime ended with failed"):
        asyncio.run(service.run(request, run))

    assert run.status == RuntimeRunStatus.FAILED
    assert run.last_decision is not None
    assert run.last_decision.action == DecisionAction.FAIL
