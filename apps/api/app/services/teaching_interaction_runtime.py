from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEventType
from app.contracts.learning import LearningActionRequest
from app.models.entities import TaskModel
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeController,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
)
from app.services.event_service import append_task_event
from app.services.teaching_interaction import TeachingInteractionService


@dataclass(frozen=True)
class TeachingRuntimeOutcome:
    run_id: str
    interaction_id: str
    status: str
    message: str
    teaching: dict[str, Any]
    approval_required: bool = False


class TeachingInteractionRuntimeService:
    """Run student feedback through a durable Runtime interaction DAG.

    The existing teaching domain service remains the compatibility business
    operation. This adapter makes the feedback observation, mutation,
    verification, and teacher approval decision durable without calling a
    Provider from the learning API route.
    """

    agent_id = "TEACHING_INTERACTION_V1"
    # Capability identity is independent from the Runtime plan version.  It
    # is intentionally declared here so release readiness never derives it
    # from a canary artifact or from ``plan_version``.
    agent_version = "learning-agent-v1"
    run_kind = "teaching_interaction"
    plan_version = "teaching-interaction-v1"
    observe_node_id = "teaching.feedback.observe"
    apply_node_id = "teaching.feedback.apply"
    verify_node_id = "teaching.feedback.verify"
    approval_node_id = "teaching.feedback.approval"

    def __init__(
        self,
        teaching_interactions: TeachingInteractionService,
        *,
        enabled: bool,
    ) -> None:
        self.teaching_interactions = teaching_interactions
        self.enabled = enabled

    def supports(self, request: LearningActionRequest) -> bool:
        return self.enabled and request.action in {
            "request_more_hint",
            "submit_check_response",
            "switch_to_direct_answer",
        }

    async def execute(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        *,
        interaction_id: str,
    ) -> TeachingRuntimeOutcome:
        if not self.supports(request):
            raise ValueError("teaching interaction Runtime is not enabled")
        plan = self.build_plan(task.id, request)
        run = AgentRun(
            run_id=uuid4().hex,
            task_id=task.id,
            goal=f"teaching interaction: {request.action}",
            plan=plan,
            request_snapshot={
                "learning_action": request.model_dump(mode="json"),
                "interaction_id": interaction_id,
            },
        )
        await AgentRunRepository(session).create(
            run,
            agent_id=self.agent_id,
            provider="local",
            workflow_version=self.plan_version,
            run_kind=self.run_kind,
        )
        return await self._drive(session, task, request, run)

    async def approve(
        self,
        session: AsyncSession,
        run_id: str,
        *,
        user_id: str,
        expected_state_version: int | None = None,
    ) -> TeachingRuntimeOutcome:
        repository = AgentRunRepository(session)
        model = await repository.get(run_id, for_update=True)
        if model is None or model.run_kind != self.run_kind:
            raise ValueError("teaching interaction Runtime run not found")
        task = await session.get(TaskModel, model.task_id)
        if task is None or task.user_id != user_id:
            raise ValueError("teaching interaction Runtime run is not owned")
        if model.status != RuntimeRunStatus.WAITING_APPROVAL.value:
            raise ValueError("teaching interaction Runtime is not awaiting approval")
        if (
            expected_state_version is not None
            and model.state_version != expected_state_version
        ):
            raise ValueError("teaching interaction Runtime state version changed")
        run = await repository.restore(run_id)
        if run is None:
            raise ValueError("teaching interaction Runtime checkpoint is missing")
        request_payload = run.request_snapshot.get("learning_action")
        if not isinstance(request_payload, dict):
            raise ValueError("teaching interaction request snapshot is missing")
        request = LearningActionRequest.model_validate(request_payload)
        await repository.request_control(
            run_id,
            "",
            control_data={"approved": True},
        )
        run.control_request = ""
        run.control_data = {"approved": True}
        return await self._drive(session, task, request, run)

    def build_plan(
        self, task_id: str, request: LearningActionRequest
    ) -> AgentRunPlan:
        return AgentRunPlan(
            plan_id=f"teaching-interaction:{task_id}:{request.action}",
            version=self.plan_version,
            goal=f"teaching interaction: {request.action}",
            nodes=[
                RuntimeNode(
                    node_id=self.observe_node_id,
                    node_type="tool",
                    handler_id="teaching.feedback.observe",
                    timeout_ms=10_000,
                ),
                RuntimeNode(
                    node_id=self.apply_node_id,
                    node_type="workflow",
                    handler_id="teaching.feedback.apply",
                    depends_on=[self.observe_node_id],
                    timeout_ms=30_000,
                ),
                RuntimeNode(
                    node_id=self.verify_node_id,
                    node_type="verification",
                    handler_id="teaching.feedback.verify",
                    depends_on=[self.apply_node_id],
                    timeout_ms=10_000,
                ),
                RuntimeNode(
                    node_id=self.approval_node_id,
                    node_type="tool",
                    handler_id="teaching.feedback.approval",
                    depends_on=[self.verify_node_id],
                    timeout_ms=10_000,
                ),
            ],
            success_criteria=[
                "feedback_observed",
                "teaching_state_updated",
                "learning_feedback_verified",
            ],
        )

    async def _drive(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        run: AgentRun,
    ) -> TeachingRuntimeOutcome:
        payload = self._restore_payload(run)
        registry = RuntimeHandlerRegistry()

        def observe_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "action": request.action,
                    "student_feedback_present": bool(request.student_answer.strip()),
                    "source_task_id": task.id,
                },
            )

        async def apply_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            message, teaching = await self.teaching_interactions.act(
                session, task, request
            )
            response_payload = {
                "message": message,
                "teaching": teaching,
                "action": request.action,
            }
            return RuntimeObservation(
                node_id=node.node_id,
                facts={"interaction_payload": response_payload},
            )

        def verify_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            current = payload or self._restore_payload(run)
            if current is None:
                raise RuntimeNodeError(
                    "teaching_interaction_result_missing",
                    "teaching interaction result is missing",
                )
            teaching = current.get("teaching")
            teaching_data = teaching if isinstance(teaching, dict) else {}
            verification = teaching_data.get("verification")
            verification_data = (
                verification if isinstance(verification, dict) else {}
            )
            approval_required = bool(
                verification_data.get("manual_review_required")
                or teaching_data.get("requires_manual_review")
            )
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "passed": True,
                    "action": request.action,
                    "approval_required": approval_required,
                    "verification_status": str(
                        verification_data.get("overall_status", "not_checked")
                    ),
                    "learning_feedback_observed": request.action
                    == "submit_check_response",
                    "teaching_state_updated": True,
                },
            )

        def approval_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            return RuntimeObservation(
                node_id=node.node_id,
                facts={"approved": True, "approval_scope": "teacher_review"},
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="teaching.feedback.observe",
                kind="tool",
                max_timeout_ms=10_000,
            ),
            observe_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="teaching.feedback.apply",
                kind="workflow",
                side_effecting=True,
                replay_safe=False,
                max_timeout_ms=30_000,
            ),
            apply_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="teaching.feedback.verify",
                kind="tool",
                max_timeout_ms=10_000,
            ),
            verify_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="teaching.feedback.approval",
                kind="tool",
                requires_approval=True,
                max_timeout_ms=10_000,
            ),
            approval_handler,
        )

        def decide(current: AgentRun) -> RuntimeDecision:
            observe = current.nodes[self.observe_node_id]
            apply = current.nodes[self.apply_node_id]
            verify = current.nodes[self.verify_node_id]
            if observe.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[self.observe_node_id],
                    reason_codes=["teaching_feedback_observation_required"],
                )
            if apply.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[self.apply_node_id],
                    reason_codes=["teaching_feedback_action_required"],
                )
            if verify.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[self.verify_node_id],
                    reason_codes=["teaching_feedback_verification_required"],
                )
            verification = verify.observation
            approval_required = bool(
                verification
                and verification.facts.get("approval_required") is True
            )
            approval = current.nodes[self.approval_node_id]
            if approval_required:
                if approval.status not in {
                    RuntimeNodeStatus.SUCCEEDED,
                    RuntimeNodeStatus.SKIPPED,
                }:
                    return RuntimeDecision(
                        action=DecisionAction.EXECUTE,
                        node_ids=[self.approval_node_id],
                        reason_codes=["teacher_review_required"],
                    )
            elif approval.status in {
                RuntimeNodeStatus.PENDING,
                RuntimeNodeStatus.READY,
            }:
                skipped = RuntimeObservation(
                    node_id=self.approval_node_id,
                    facts={"approved": False, "approval_not_required": True},
                )
                approval.status = RuntimeNodeStatus.SKIPPED
                approval.effect_status = RuntimeEffectStatus.COMPLETED
                approval.observation = skipped
                approval.completed_at = datetime.now(UTC)
                current.observations.append(skipped)
            return RuntimeDecision(
                action=DecisionAction.FINISH,
                reason_codes=["teaching_feedback_runtime_verified"],
            )

        async def checkpoint(current: AgentRun) -> None:
            await AgentRunRepository(session).save_checkpoint(current)

        async def event(event: str, current: AgentRun, node_id: str) -> None:
            await append_task_event(
                session,
                task.id,
                AgentEventType.AGENT_PROGRESS,
                agent_id=self.agent_id,
                data={
                    "stage_id": "teaching_runtime",
                    "runtime_event": event,
                    "runtime_run_id": current.run_id,
                    "node_id": node_id,
                    "state_version": current.state_version,
                },
            )

        async def decision_event(
            current: AgentRun, decision: RuntimeDecision
        ) -> None:
            await append_task_event(
                session,
                task.id,
                AgentEventType.AGENT_PROGRESS,
                agent_id=self.agent_id,
                data={
                    "stage_id": "teaching_runtime_decision",
                    "runtime_run_id": current.run_id,
                    "action": decision.action.value,
                    "reason_codes": list(decision.reason_codes),
                    "approval_scope": decision.approval_scope,
                    "state_version": current.state_version,
                },
            )

        controller = RuntimeController(
            PlanExecutor(registry, checkpoint_hook=checkpoint, event_hook=event),
            decide,
            checkpoint_hook=checkpoint,
            decision_event_hook=decision_event,
        )
        await controller.run(run)
        payload = self._restore_payload(run) or {}
        verification = self._verification_observation(run)
        return TeachingRuntimeOutcome(
            run_id=run.run_id,
            interaction_id=str(run.request_snapshot.get("interaction_id", "")),
            status=run.status.value,
            message=str(payload.get("message", "")),
            teaching=(
                cast(dict[str, Any], payload["teaching"])
                if isinstance(payload.get("teaching"), dict)
                else {}
            ),
            approval_required=bool(
                verification and verification.facts.get("approval_required") is True
            ),
        )

    @staticmethod
    def _restore_payload(run: AgentRun) -> dict[str, Any] | None:
        for observation in reversed(run.observations):
            payload = observation.facts.get("interaction_payload")
            if isinstance(payload, dict):
                return dict(payload)
        return None

    def _verification_observation(
        self, run: AgentRun
    ) -> RuntimeObservation | None:
        state = run.nodes.get(self.verify_node_id)
        return state.observation if state is not None else None
