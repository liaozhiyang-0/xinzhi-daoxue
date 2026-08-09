from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEventType
from app.contracts.learning import (
    LearningActionRequest,
    LearningActionResponse,
)
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

LearningProgressExecutor = Callable[
    [AsyncSession, TaskModel, LearningActionRequest, str],
    Awaitable[LearningActionResponse],
]


@dataclass(frozen=True)
class LearningProgressRuntimeOutcome:
    run_id: str
    interaction_id: str
    status: str
    response: LearningActionResponse
    approval_required: bool = False


class LearningProgressRuntimeService:
    """Persist the learning-progress side effects as an Agent Runtime run.

    The domain implementation is injected as a compatibility executor. The
    Runtime owns the durable observation, mutation boundary, verification,
    and human-review decision so the migration does not duplicate mastery
    policy or retest rules.
    """

    agent_id = "LEARNING_PROGRESS_V1"
    # Capability identity is independent from the Runtime plan version.  It
    # is intentionally declared here so release readiness never derives it
    # from a canary artifact or from ``plan_version``.
    agent_version = "learning-agent-v1"
    run_kind = "learning_progress"
    plan_version = "learning-progress-v1"
    control_scope = "learning_loop"
    supports_pause = True
    supports_resume = True
    supports_approval = True
    supports_input = True
    observe_node_id = "learning.progress.observe"
    apply_node_id = "learning.progress.apply"
    verify_node_id = "learning.progress.verify"
    approval_node_id = "learning.progress.approval"

    def __init__(
        self,
        action_executor: LearningProgressExecutor,
        *,
        enabled: bool,
    ) -> None:
        self.action_executor = action_executor
        self.enabled = enabled

    def supports(self, request: LearningActionRequest) -> bool:
        return self.enabled and request.action in {
            "submit_attempt_revision",
            "start_retest",
            "complete_retest",
            "dismiss_retest",
        }

    async def execute(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        *,
        interaction_id: str,
    ) -> LearningProgressRuntimeOutcome:
        if not self.supports(request):
            raise ValueError("learning progress Runtime is not enabled")
        run = AgentRun(
            run_id=uuid4().hex,
            task_id=task.id,
            goal=f"learning progress: {request.action}",
            plan=self.build_plan(task.id, request),
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
    ) -> LearningProgressRuntimeOutcome:
        repository = AgentRunRepository(session)
        model = await repository.get(run_id, for_update=True)
        if model is None or model.run_kind != self.run_kind:
            raise ValueError("learning progress Runtime run not found")
        task = await session.get(TaskModel, model.task_id)
        if task is None or (user_id and task.user_id != user_id):
            raise ValueError("learning progress Runtime run is not owned")
        if model.status != RuntimeRunStatus.WAITING_APPROVAL.value:
            raise ValueError("learning progress Runtime is not awaiting approval")
        if (
            expected_state_version is not None
            and model.state_version != expected_state_version
        ):
            raise ValueError("learning progress Runtime state version changed")
        run = await repository.restore(run_id)
        if run is None:
            raise ValueError("learning progress Runtime checkpoint is missing")
        payload = run.request_snapshot.get("learning_action")
        if not isinstance(payload, dict):
            raise ValueError("learning progress Runtime request snapshot is missing")
        request = LearningActionRequest.model_validate(payload)
        await repository.request_control(
            run_id,
            "",
            control_data={"approved": True},
        )
        run.control_request = ""
        run.control_data = {"approved": True}
        return await self._drive(session, task, request, run)

    async def continue_run(
        self,
        session: AsyncSession,
        task: TaskModel,
        run: AgentRun,
    ) -> LearningProgressRuntimeOutcome:
        """Resume a checkpoint after pause or user input was persisted."""

        payload = run.request_snapshot.get("learning_action")
        if not isinstance(payload, dict):
            raise ValueError("learning progress Runtime request snapshot is missing")
        request = LearningActionRequest.model_validate(payload)
        return await self._drive(session, task, request, run)

    def build_plan(
        self, task_id: str, request: LearningActionRequest
    ) -> AgentRunPlan:
        return AgentRunPlan(
            plan_id=f"learning-progress:{task_id}:{request.action}",
            version=self.plan_version,
            goal=f"learning progress: {request.action}",
            nodes=[
                RuntimeNode(
                    node_id=self.observe_node_id,
                    node_type="tool",
                    handler_id="learning.progress.observe",
                    timeout_ms=10_000,
                ),
                RuntimeNode(
                    node_id=self.apply_node_id,
                    node_type="workflow",
                    handler_id="learning.progress.apply",
                    depends_on=[self.observe_node_id],
                    timeout_ms=60_000,
                ),
                RuntimeNode(
                    node_id=self.verify_node_id,
                    node_type="verification",
                    handler_id="learning.progress.verify",
                    depends_on=[self.apply_node_id],
                    timeout_ms=10_000,
                ),
                RuntimeNode(
                    node_id=self.approval_node_id,
                    node_type="tool",
                    handler_id="learning.progress.approval",
                    depends_on=[self.verify_node_id],
                    timeout_ms=10_000,
                ),
            ],
            success_criteria=[
                "learning_action_observed",
                "learning_progress_applied",
                "learning_progress_verified",
            ],
        )

    async def _drive(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        run: AgentRun,
    ) -> LearningProgressRuntimeOutcome:
        request = self._apply_runtime_input(request, run)
        registry = RuntimeHandlerRegistry()

        def observe_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "action": request.action,
                    "source_task_id": task.id,
                    "student_answer_present": bool(request.student_answer.strip()),
                    "has_attempt_payload": isinstance(
                        request.payload.get("attempt"), dict
                    ),
                    "idempotency_key": request.idempotency_key,
                },
            )

        async def apply_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            response = await self.action_executor(
                session,
                task,
                request,
                str(run.request_snapshot.get("interaction_id", "")),
            )
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "learning_progress_payload": response.model_dump(mode="json"),
                },
            )

        def verify_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            payload = self._restore_payload(run)
            if payload is None:
                raise RuntimeNodeError(
                    "learning_progress_result_missing",
                    "learning progress result is missing",
                )
            response = LearningActionResponse.model_validate(payload)
            attempt_status = (
                response.attempt.verification_status if response.attempt else None
            )
            uptake_status = (
                response.feedback_uptake.status.value
                if response.feedback_uptake is not None
                else None
            )
            approval_required = attempt_status == "manual_review" or (
                uptake_status == "indeterminate"
            )
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "passed": True,
                    "action": request.action,
                    "attempt_id": response.attempt.attempt_id
                    if response.attempt
                    else "",
                    "attempt_verification_status": attempt_status or "",
                    "feedback_uptake_status": uptake_status or "not_applicable",
                    "mastery_evidence_count": len(response.mastery_evidence),
                    "retest_plan_count": len(response.retest_plans),
                    "approval_required": approval_required,
                },
            )

        def approval_handler(
            _current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            return RuntimeObservation(
                node_id=node.node_id,
                facts={"approved": True, "approval_scope": "learning_progress"},
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="learning.progress.observe",
                kind="tool",
                max_timeout_ms=10_000,
            ),
            observe_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="learning.progress.apply",
                kind="workflow",
                side_effecting=True,
                replay_safe=False,
                max_timeout_ms=60_000,
            ),
            apply_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="learning.progress.verify",
                kind="tool",
                max_timeout_ms=10_000,
            ),
            verify_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="learning.progress.approval",
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
                    reason_codes=["learning_progress_observation_required"],
                )
            if apply.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[self.apply_node_id],
                    reason_codes=["learning_progress_action_required"],
                )
            if verify.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[self.verify_node_id],
                    reason_codes=["learning_progress_verification_required"],
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
                        reason_codes=["learning_progress_review_required"],
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
                reason_codes=["learning_progress_runtime_verified"],
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
                    "stage_id": "learning_progress_runtime",
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
                    "stage_id": "learning_progress_runtime_decision",
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
        payload = self._restore_payload(run)
        if payload is None:
            raise ValueError("learning progress Runtime result is missing")
        response = LearningActionResponse.model_validate(payload)
        verification = run.nodes[self.verify_node_id].observation
        return LearningProgressRuntimeOutcome(
            run_id=run.run_id,
            interaction_id=str(run.request_snapshot.get("interaction_id", "")),
            status=run.status.value,
            response=response,
            approval_required=bool(
                verification and verification.facts.get("approval_required") is True
            ),
        )

    @staticmethod
    def _apply_runtime_input(
        request: LearningActionRequest, run: AgentRun
    ) -> LearningActionRequest:
        raw_input = run.control_data.get("user_input")
        if not isinstance(raw_input, Mapping):
            return request
        payload = dict(request.payload)
        payload["runtime_user_input"] = dict(raw_input)
        return request.model_copy(update={"payload": payload})

    @staticmethod
    def _restore_payload(run: AgentRun) -> dict[str, Any] | None:
        for observation in reversed(run.observations):
            payload = observation.facts.get("learning_progress_payload")
            if isinstance(payload, dict):
                return dict(payload)
        return None
