"""Runtime adapter for the assignment-review business Agent."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any, cast

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.runtime import (
    AgentRun,
    DecisionAction,
    PlanProposalProvider,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeNodeStatus,
    RuntimeRunStatus,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService


class AssignmentReviewRuntimeService(GeneralQuestionRuntimeService):
    """Run assignment review through the shared observable Runtime DAG."""

    agent_id = "TEACH_02_ASSIGNMENT_REVIEW_V1"
    observe_node_id = "assignment.observe"
    retrieve_node_id = "assignment.retrieve"
    tool_node_id = "assignment.tool"
    execute_node_id = "assignment.execute"
    verify_node_id = "assignment.verify"
    runtime_option_key = "assignment_review_runtime"
    runtime_plan_prefix = "assignment-review-runtime"
    runtime_plan_version = "assignment-review-v1"
    runtime_name = "assignment_review"
    observe_handler_id = "assignment.review.observe"
    retrieve_handler_id = "assignment.review.retrieve"
    tool_handler_prefix = "assignment.review.tool"
    execute_handler_id = "assignment.review.execute"
    verify_handler_id = "assignment.review.verify"
    approval_scope = "assignment_review"
    approval_control_key = "assignment_review_approval_granted"

    _REVIEW_STATUS_VALUES = frozenset(
        {
            "degraded",
            "manual_review",
            "needs_review",
            "partial",
            "review_required",
            "uncertain",
        }
    )
    _REVIEW_STATUS_KEYS = frozenset(
        {
            "output_status",
            "quality_status",
            "review_status",
            "status",
            "verification_status",
        }
    )

    async def run(
        self,
        request: AgentRequest,
        run: AgentRun,
        context: Any = None,
        checkpoint_hook: Callable[[AgentRun], Any] | None = None,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        control_provider: Callable[[AgentRun], Any] | None = None,
        decision_event_hook: Callable[[AgentRun, RuntimeDecision], Any]
        | None = None,
        plan_proposal_provider: PlanProposalProvider | None = None,
    ) -> AgentResult:
        """Run assignment review with a durable, one-shot approval gate."""

        if (
            self._approval_required_for_run(run)
            and run.control_data.get("approved") is True
        ):
            control_data = dict(run.control_data)
            control_data.pop("approved", None)
            control_data[self.approval_control_key] = True
            run.control_data = control_data
            self._mark_verification_approved(run)

        async def assignment_control(current: AgentRun) -> RuntimeDecision | None:
            if control_provider is not None:
                decision = control_provider(current)
                if inspect.isawaitable(decision):
                    decision = await decision
                typed_decision = cast(RuntimeDecision | None, decision)
                if typed_decision is not None:
                    return typed_decision
            if (
                self._approval_required_for_run(current)
                and current.control_data.get(self.approval_control_key) is not True
            ):
                return RuntimeDecision(
                    action=DecisionAction.REQUEST_APPROVAL,
                    approval_scope=self.approval_scope,
                    reason_codes=["assignment_review_quality_gate"],
                )
            return None

        return await super().run(
            request,
            run,
            context=context,
            checkpoint_hook=checkpoint_hook,
            event_hook=event_hook,
            control_provider=assignment_control,
            decision_event_hook=decision_event_hook,
            plan_proposal_provider=plan_proposal_provider,
        )

    def _approval_required_for_run(self, run: AgentRun) -> bool:
        """Return true only for a passed verification awaiting teacher review."""

        try:
            _, _, _, _, verify_node_id = self._current_node_ids(run)
        except (StopIteration, RuntimeError):
            return False
        verify_state = run.nodes[verify_node_id]
        if verify_state.status not in {
            RuntimeNodeStatus.PARTIAL,
            RuntimeNodeStatus.SUCCEEDED,
        }:
            return False
        verification = verify_state.observation
        if verification is None:
            return False
        result = self._restore_result(run)
        if result is None or not self._requires_review(result):
            return False
        return (
            verify_state.status == RuntimeNodeStatus.PARTIAL
            or verification.facts.get("passed") is True
        )

    def _mark_verification_approved(self, run: AgentRun) -> None:
        """Convert a checkpointed review gate into a completed verification."""

        _, _, _, _, verify_node_id = self._current_node_ids(run)
        state = run.nodes[verify_node_id]
        if state.status != RuntimeNodeStatus.PARTIAL:
            return
        observation = state.observation
        if observation is not None:
            facts = dict(observation.facts)
            facts.update(
                {
                    "passed": True,
                    "approval_granted": True,
                    "replan_required": False,
                }
            )
            approved = observation.model_copy(update={"facts": facts})
            state.observation = approved
            for index in range(len(run.observations) - 1, -1, -1):
                if run.observations[index].node_id == verify_node_id:
                    run.observations[index] = approved
                    break
        state.status = RuntimeNodeStatus.SUCCEEDED
        state.effect_status = RuntimeEffectStatus.COMPLETED
        state.error_code = ""
        run.status = RuntimeRunStatus.RUNNING
        run.completed_at = None

    @classmethod
    def _requires_review(cls, result: AgentResult) -> bool:
        if result.status == AgentResultStatus.FAILED:
            return False
        for container in (result.business_data, result.structured_result):
            if not isinstance(container, Mapping):
                continue
            if container.get("review_required") is True:
                return True
            for key, value in container.items():
                if (
                    key in cls._REVIEW_STATUS_KEYS
                    and isinstance(value, str)
                    and value.strip().casefold() in cls._REVIEW_STATUS_VALUES
                ):
                    return True
        quality_status = result.metrics.quality_status.strip().casefold()
        return quality_status in cls._REVIEW_STATUS_VALUES

    def _is_valid_result(self, result: AgentResult) -> bool:
        if not super()._is_valid_result(result):
            return False
        required_fields = {
            "correctness",
            "correct_parts",
            "errors",
            "teacher_feedback",
            "review_required",
        }
        return (
            required_fields <= set(result.business_data)
            and not self._requires_review(result)
        )
