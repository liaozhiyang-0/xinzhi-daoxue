from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any, Literal, cast

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.runtime import (
    AgentRun,
    DecisionAction,
    PlanProposalProvider,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeRunStatus,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService


class LessonPrepRuntimeService(GeneralQuestionRuntimeService):
    """Run lesson preparation through the shared Runtime execute/verify kernel.

    Lesson plans have a stronger business contract than a generic answer. The
    adapter keeps that contract local to TEACH_01 while reusing the shared
    execution, checkpoint, and iteration-budget machinery.
    """

    agent_id = "TEACH_01_LESSON_PREP_V1"
    observe_node_id = "lesson.observe"
    retrieve_node_id = "lesson.retrieve"
    tool_node_id = "lesson.tool"
    execute_node_id = "lesson.execute"
    verify_node_id = "lesson.verify"
    runtime_option_key = "lesson_prep_runtime"
    runtime_plan_prefix = "lesson-prep-runtime"
    runtime_plan_version = "lesson-prep-v1"
    runtime_name = "lesson_prep"
    observe_handler_id = "lesson.prep.observe"
    retrieve_handler_id = "lesson.prep.retrieve"
    tool_handler_prefix = "lesson.prep.tool"
    execute_handler_id = "lesson.prep.execute"
    verify_handler_id = "lesson.prep.verify"
    approval_scope = "lesson_prep.quality_gate"
    approval_control_key = "lesson_prep_approval_granted"

    _REQUIRED_FIELDS = (
        "learning_objectives",
        "lesson_flow",
        "activities",
        "formative_assessment",
    )
    _QUALITY_MARKERS = frozenset(
        {
            "n/a",
            "na",
            "none",
            "placeholder",
            "tbd",
            "todo",
            "待补充",
            "待完善",
            "待确定",
            "暂无",
        }
    )
    _REVIEW_STATUS_VALUES = frozenset(
        {"degraded", "manual_review", "needs_review", "partial", "review"}
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
        """Run the lesson-plan gate without replaying approved execution."""

        if (
            self._approval_required_for_run(run)
            and run.control_data.get("approved") is True
        ):
            control_data = dict(run.control_data)
            control_data.pop("approved", None)
            control_data[self.approval_control_key] = True
            run.control_data = control_data
            self._mark_verification_approved(run)

        async def lesson_control(current: AgentRun) -> RuntimeDecision | None:
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
                    reason_codes=["lesson_prep_quality_gate"],
                )
            return None

        try:
            return await super().run(
                request,
                run,
                context=context,
                checkpoint_hook=checkpoint_hook,
                event_hook=event_hook,
                control_provider=lesson_control,
                decision_event_hook=decision_event_hook,
                plan_proposal_provider=plan_proposal_provider,
            )
        except RuntimeNodeError:
            # A structurally invalid result must not escape as a successful
            # AgentResult merely because the shared controller exhausted its
            # bounded replans.
            if run.status == RuntimeRunStatus.FAILED:
                restored = self._restore_result(run)
                if restored is not None:
                    return restored.model_copy(
                        update={
                            "status": AgentResultStatus.FAILED,
                            "warnings": [
                                *restored.warnings,
                                "lesson_prep_runtime_failed_closed",
                            ][:20],
                        }
                    )
            raise

    def _approval_required_for_run(self, run: AgentRun) -> bool:
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
        result = self._restore_result(run)
        if verification is None or result is None:
            return False
        return (
            self._verification_state(result) == "approval"
            and (
                verify_state.status == RuntimeNodeStatus.PARTIAL
                or verification.facts.get("passed") is True
            )
        )

    def _verification_approval_decision(
        self, run: AgentRun
    ) -> RuntimeDecision | None:
        if not self._approval_required_for_run(run):
            return None
        return RuntimeDecision(
            action=DecisionAction.REQUEST_APPROVAL,
            approval_scope=self.approval_scope,
            reason_codes=["lesson_prep_quality_gate"],
        )

    def _mark_verification_approved(self, run: AgentRun) -> None:
        """Complete only the checkpointed quality gate after approval."""

        _, _, _, _, verify_node_id = self._current_node_ids(run)
        state = run.nodes[verify_node_id]
        if state.status != RuntimeNodeStatus.PARTIAL:
            return
        observation = state.observation
        if observation is not None:
            approved = observation.model_copy(
                update={
                    "facts": {
                        **observation.facts,
                        "passed": True,
                        "replan_required": False,
                        "requires_approval": False,
                        "approval_granted": True,
                    }
                }
            )
            state.observation = approved
            run.observations.append(approved)
            run.verification_history.append(approved)
        state.status = RuntimeNodeStatus.SUCCEEDED
        state.effect_status = RuntimeEffectStatus.COMPLETED
        state.error_code = ""
        run.status = RuntimeRunStatus.RUNNING
        run.completed_at = None

    @classmethod
    def _verification_state(
        cls, result: AgentResult
    ) -> Literal["valid", "approval", "replan"]:
        if result.status != AgentResultStatus.COMPLETED or not result.answer.strip():
            return "replan"

        fields: dict[str, list[str]] = {}
        for field in cls._REQUIRED_FIELDS:
            raw_value = result.business_data.get(field)
            items = cls._field_items(raw_value)
            if items is None:
                # An explicitly empty section is still a reviewable answer:
                # replanning the same deterministic request can reproduce the
                # omission and trap the Runtime in an approval/replan loop.
                # A missing or malformed section remains a structural failure
                # and must use the bounded replan path.
                if isinstance(raw_value, (list, tuple)):
                    return "approval"
                return "replan"
            fields[field] = items

        if cls._has_quality_warning(result, fields):
            return "approval"
        return "valid"

    @staticmethod
    def _field_items(value: Any) -> list[str] | None:
        if not isinstance(value, (list, tuple)) or not value:
            return None
        items = [item.strip() for item in value if isinstance(item, str)]
        if len(items) != len(value) or not all(items):
            return None
        return items

    @classmethod
    def _has_quality_warning(
        cls, result: AgentResult, fields: Mapping[str, list[str]]
    ) -> bool:
        if len(fields["lesson_flow"]) < 2:
            return True
        if any(len(item) < 3 for items in fields.values() for item in items):
            return True
        if any(
            item.casefold() in cls._QUALITY_MARKERS
            for items in fields.values()
            for item in items
        ):
            return True
        data = result.business_data
        if data.get("review_required") is True:
            return True
        for key in ("quality_status", "review_status", "verification_status"):
            value = data.get(key)
            if isinstance(value, str) and value.strip().casefold() in (
                cls._REVIEW_STATUS_VALUES
            ):
                return True
        return result.metrics.quality_status.strip().casefold() in (
            cls._REVIEW_STATUS_VALUES
        )

    def _is_valid_result(self, result: AgentResult) -> bool:
        return self._verification_state(result) == "valid"
