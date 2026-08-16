from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import AgentEventType
from app.models import AgentPlanProposalModel, TaskStatus
from app.repositories import AgentRunRepository, TaskRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    RuntimeDecision,
    RuntimePlanProposal,
    RuntimeRunStatus,
    to_task_event,
)
from app.services.event_service import append_task_events
from app.services.runtime_plan_proposals import RuntimePlanProposalService

RuntimePendingEvent = tuple[AgentEventType, dict[str, Any]]


class RuntimePersistenceHooks:
    """Persist Runtime checkpoints, controls, proposals, and ordered events."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory
        self._event_buffers: dict[str, list[RuntimePendingEvent]] = {}

    async def checkpoint(self, run: AgentRun) -> None:
        pending_events = list(self._event_buffers.get(run.run_id, []))
        async with self.session_factory() as db:
            repository = AgentRunRepository(db)
            runtime_model = await repository.get(run.run_id, for_update=True)
            if runtime_model is None:
                raise ValueError(f"runtime run does not exist: {run.run_id}")
            self._merge_control_data(run, runtime_model)
            task = await TaskRepository(db).get(run.task_id, for_update=True)
            if task is not None:
                self._project_waiting_status(run, task)
            persisted_events = await append_task_events(
                db,
                run.task_id,
                pending_events,
                task=task,
            )
            event_sequence = (
                persisted_events[-1].sequence if persisted_events else None
            )
            await repository.save_checkpoint(
                run,
                model=runtime_model,
                event_sequence=event_sequence,
            )
            proposal_id = run.control_data.get("plan_proposal_id")
            if isinstance(proposal_id, str) and proposal_id:
                proposal_model = await db.get(AgentPlanProposalModel, proposal_id)
                if (
                    proposal_model is not None
                    and proposal_model.run_id == run.run_id
                    and proposal_model.status == "pending"
                ):
                    proposal_model.state_version = run.state_version
            await db.commit()
        if pending_events:
            current = self._event_buffers.get(run.run_id)
            if current is not None:
                del current[: len(pending_events)]
                if not current:
                    self._event_buffers.pop(run.run_id, None)

    async def control(self, run: AgentRun) -> RuntimeDecision | None:
        async with self.session_factory() as db:
            runtime_model = await AgentRunRepository(db).get(run.run_id)
            if runtime_model is None or runtime_model.control_request != "pause":
                return None
        return RuntimeDecision(
            action=DecisionAction.PAUSE,
            reason_codes=["pause_requested_by_user"],
        )

    async def propose_plan(
        self,
        run: AgentRun,
        decision: RuntimeDecision,
        plan: AgentRunPlan,
    ) -> RuntimePlanProposal:
        async with self.session_factory() as db:
            proposal = await RuntimePlanProposalService(db).create(
                run.task_id,
                run.run_id,
                plan,
                reason_codes=decision.reason_codes,
                rationale=(
                    "Runtime verification requested a bounded replacement "
                    "plan; explicit review is required before application."
                ),
                approval_required=True,
                expected_state_version=run.state_version,
                target_iteration=run.iteration,
            )
        run.state_version = proposal.state_version
        run.control_data = {
            **run.control_data,
            "plan_proposal_id": proposal.proposal_id,
            "plan_proposal_status": "pending",
        }
        run.control_request = ""
        return proposal

    async def append_node_event(
        self,
        event: str,
        run: AgentRun,
        node_id: str,
    ) -> None:
        event_type, data = to_task_event(event, run, node_id)
        data["runtime_event"] = event
        self._event_buffers.setdefault(run.run_id, []).append((event_type, data))

    async def append_decision_event(
        self,
        run: AgentRun,
        decision: RuntimeDecision,
    ) -> None:
        event_type = {
            DecisionAction.ASK_USER: AgentEventType.AGENT_INPUT_REQUIRED,
            DecisionAction.REQUEST_APPROVAL: AgentEventType.AGENT_PROGRESS,
            DecisionAction.PAUSE: AgentEventType.AGENT_PROGRESS,
        }.get(decision.action)
        if event_type is None:
            return
        data: dict[str, object] = {
            "runtime_run_id": run.run_id,
            "action": decision.action.value,
            "reason_codes": list(decision.reason_codes),
            "state_version": run.state_version,
        }
        if decision.user_prompt:
            data["user_prompt"] = decision.user_prompt
        if decision.approval_scope:
            data["approval_scope"] = decision.approval_scope
        self._event_buffers.setdefault(run.run_id, []).append((event_type, data))

    def discard(self, run_id: str) -> None:
        self._event_buffers.pop(run_id, None)

    @staticmethod
    def _merge_control_data(run: AgentRun, runtime_model: Any) -> None:
        durable = dict(runtime_model.control_data or {})
        if run.status == RuntimeRunStatus.PAUSED:
            suspended_child = durable.get("suspended_child_run_id")
            run.control_request = ""
            merged = {**durable, **run.control_data}
            if (
                "suspended_child_run_id" not in merged
                and isinstance(suspended_child, str)
                and suspended_child
            ):
                merged["suspended_child_run_id"] = suspended_child
            run.control_data = merged
            return
        if (
            run.status == RuntimeRunStatus.RUNNING
            and durable.get("approved") is True
            and run.control_data.get("approved") is not True
        ):
            run.control_request = ""
            merged = {**durable, **run.control_data}
            merged.pop("approved", None)
            merged.pop("approved_scope", None)
            merged.pop("approval_scope", None)
            run.control_data = merged
            return
        run.control_request = runtime_model.control_request
        run.control_data = {**durable, **run.control_data}

    @staticmethod
    def _project_waiting_status(run: AgentRun, task: Any) -> None:
        if run.status in {RuntimeRunStatus.PAUSED, RuntimeRunStatus.WAITING_INPUT}:
            task.status = TaskStatus.WAITING_USER
        elif run.status == RuntimeRunStatus.WAITING_APPROVAL:
            task.status = TaskStatus.WAITING_REVIEW
        elif run.status == RuntimeRunStatus.RUNNING and task.status in {
            TaskStatus.WAITING_USER,
            TaskStatus.WAITING_REVIEW,
        }:
            task.status = TaskStatus.RUNNING
