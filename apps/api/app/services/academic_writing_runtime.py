"""Runtime adapter for the academic-writing business Agent."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any, Literal

from app.contracts import AgentRequest, AgentResult
from app.runtime import (
    AgentRun,
    ControlProvider,
    DecisionAction,
    PlanProposalProvider,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeNodeError,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService


class AcademicWritingRuntimeService(GeneralQuestionRuntimeService):
    """Run academic writing assistance through the shared Runtime DAG."""

    approval_scope = "academic_writing.citation_check"
    _PASS_CITATION_STATUSES = frozenset(
        {
            "pass",
            "passed",
            "verified",
            "clear",
            "not_required",
            "not required",
            "无需核验",
            "未提出引用要求",
            "已核验",
            "通过",
        }
    )
    _REVIEW_CITATION_MARKERS = (
        "uncertain",
        "pending",
        "review",
        "manual",
        "人工",
        "核验",
        "待核",
        "不确定",
        "需要检查",
    )

    agent_id = "RESEARCH_02_ACADEMIC_WRITING_V1"
    observe_node_id = "writing.observe"
    retrieve_node_id = "writing.retrieve"
    tool_node_id = "writing.tool"
    execute_node_id = "writing.execute"
    verify_node_id = "writing.verify"
    runtime_option_key = "academic_writing_runtime"
    runtime_plan_prefix = "academic-writing-runtime"
    runtime_plan_version = "academic-writing-v1"
    runtime_name = "academic_writing"
    observe_handler_id = "academic.writing.observe"
    retrieve_handler_id = "academic.writing.retrieve"
    tool_handler_prefix = "academic.writing.tool"
    execute_handler_id = "academic.writing.execute"
    verify_handler_id = "academic.writing.verify"

    async def run(
        self,
        request: AgentRequest,
        run: AgentRun,
        context: Any = None,
        checkpoint_hook: Callable[[AgentRun], Any] | None = None,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        control_provider: ControlProvider | None = None,
        decision_event_hook: Callable[[AgentRun, RuntimeDecision], Any] | None = None,
        plan_proposal_provider: PlanProposalProvider | None = None,
    ) -> AgentResult:
        """Add academic-writing approval semantics around the shared loop.

        The base Runtime already owns node execution, retry/replan budgets and
        durable result observations.  This adapter only adds the business
        verification policy that cannot be expressed by the generic answer
        predicate.
        """

        self._restore_approved_checkpoint(run)

        async def guarded_control(current: AgentRun) -> RuntimeDecision | None:
            if self._needs_citation_approval(current):
                return RuntimeDecision(
                    action=DecisionAction.REQUEST_APPROVAL,
                    approval_scope=self.approval_scope,
                    reason_codes=["academic_writing_citation_review_required"],
                )
            if control_provider is None:
                return None
            decision = control_provider(current)
            if inspect.isawaitable(decision):
                return await decision
            return decision

        try:
            return await super().run(
                request,
                run,
                context,
                checkpoint_hook,
                event_hook,
                guarded_control,
                decision_event_hook,
                plan_proposal_provider,
            )
        except RuntimeNodeError:
            # A completed-but-invalid AgentResult must remain a fail-closed
            # result contract when the shared controller exhausts replans.
            if run.status == RuntimeRunStatus.FAILED:
                restored = self._restore_result(run)
                if restored is not None and restored.status.value != "failed":
                    return restored.model_copy(
                        update={
                            "status": "failed",
                            "warnings": [
                                *restored.warnings,
                                "academic_writing_runtime_failed_closed",
                            ][:20],
                        }
                    )
            raise

    def _is_valid_result(self, result: AgentResult) -> bool:
        return self._verification_state(result) == "valid"

    def _verification_approval_decision(
        self, run: AgentRun
    ) -> RuntimeDecision | None:
        """Suspend on citation review before the shared loop proposes a replan."""

        if not self._needs_citation_approval(run):
            return None
        return RuntimeDecision(
            action=DecisionAction.REQUEST_APPROVAL,
            approval_scope=self.approval_scope,
            reason_codes=["academic_writing_citation_review_required"],
        )

    @classmethod
    def _verification_state(
        cls, result: AgentResult
    ) -> Literal["valid", "approval", "replan"]:
        if result.status.value != "completed" or not result.answer.strip():
            return "replan"
        data = result.business_data
        required_fields = {
            "revised_text",
            "revision_notes",
            "unsupported_claims",
            "citation_check",
        }
        if not required_fields <= set(data):
            return "replan"
        revised_text = data["revised_text"]
        notes = data["revision_notes"]
        unsupported = data["unsupported_claims"]
        if (
            not isinstance(revised_text, str)
            or not revised_text.strip()
            or not isinstance(notes, list)
            or not notes
            or not all(isinstance(item, str) and item.strip() for item in notes)
            or not isinstance(unsupported, list)
            or not all(isinstance(item, str) and item.strip() for item in unsupported)
        ):
            return "replan"

        citation_status = cls._citation_status(data["citation_check"])
        if citation_status == "review" or unsupported:
            return "approval"
        if citation_status == "passed":
            return "valid"
        return "replan"

    @classmethod
    def _citation_status(cls, value: Any) -> Literal["passed", "review", "failed"]:
        if isinstance(value, Mapping):
            value = value.get("status", value.get("result", ""))
        if not isinstance(value, str):
            return "failed"
        normalized = " ".join(value.casefold().strip().split())
        if normalized in cls._PASS_CITATION_STATUSES:
            return "passed"
        if any(marker in normalized for marker in cls._REVIEW_CITATION_MARKERS):
            return "review"
        return "failed"

    @classmethod
    def _verify_node_state(cls, run: AgentRun) -> RuntimeNodeState:
        return next(
            state
            for node_id, state in run.nodes.items()
            if node_id == cls.verify_node_id
            or node_id.startswith(f"{cls.verify_node_id}.")
        )

    @classmethod
    def _needs_citation_approval(cls, run: AgentRun) -> bool:
        state = cls._verify_node_state(run)
        result = cls._restore_result(run)
        return (
            state.status == RuntimeNodeStatus.PARTIAL
            and result is not None
            and cls._verification_state(result) == "approval"
            and not cls._approval_granted(run)
        )

    @classmethod
    def _approval_granted(cls, run: AgentRun) -> bool:
        return run.control_data.get("approved") is True and (
            run.last_decision is not None
            and run.last_decision.approval_scope == cls.approval_scope
        )

    @classmethod
    def _restore_approved_checkpoint(cls, run: AgentRun) -> None:
        """Accept an approved checkpoint without replaying the Agent call."""

        if run.status != RuntimeRunStatus.WAITING_APPROVAL or not cls._approval_granted(
            run
        ):
            return
        state = cls._verify_node_state(run)
        result = cls._restore_result(run)
        if (
            result is None
            or cls._verification_state(result) != "approval"
            or state.status != RuntimeNodeStatus.PARTIAL
        ):
            return
        observation = state.observation
        if observation is None:
            observation = RuntimeObservation(node_id=state.node_id)
        approved_observation = observation.model_copy(
            update={
                "terminal_status": RuntimeNodeStatus.SUCCEEDED,
                "facts": {
                    **observation.facts,
                    "passed": True,
                    "requires_approval": False,
                    "approval_granted": True,
                },
            }
        )
        state.status = RuntimeNodeStatus.SUCCEEDED
        state.effect_status = RuntimeEffectStatus.COMPLETED
        state.observation = approved_observation
        run.observations.append(approved_observation)
        run.verification_history.append(approved_observation)
        run.control_data = {
            key: value
            for key, value in run.control_data.items()
            if key not in {"approved", "approval_scope"}
        }
        run.status = RuntimeRunStatus.RUNNING
        run.completed_at = None
