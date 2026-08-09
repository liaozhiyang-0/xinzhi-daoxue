from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentEventType,
    AgentRequest,
    RouteDecision,
    RuntimeInputSubmission,
    RuntimeReconciliationSubmission,
    new_id,
)
from app.contracts.conversation import MessageStatus
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models import AgentRunModel, TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import AgentRunRepository, TaskRepository
from app.runtime import (
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeStateMachine,
)
from app.services.conversation_message_service import ConversationMessageService
from app.services.evaluation_attachment_cleanup import (
    cleanup_evaluation_attachments,
)
from app.services.event_service import append_task_event
from app.services.task_creation_service import TaskCreationService

RETRYABLE_FAILURES = {
    "background_task_error",
    "model_provider_error",
    "provider_error",
    "provider_timeout",
    "runner_shutdown",
    "xingchen_connection_error",
    "xingchen_timeout",
}
TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


class TaskControlService:
    def __init__(
        self, db: AsyncSession, provider: AgentProvider, settings: Settings
    ) -> None:
        self.db = db
        self.provider = provider
        self._settings = settings
        self.repository = TaskRepository(db)

    async def retry(self, task_id: str) -> TaskModel:
        original = await self.repository.get(task_id, for_update=True)
        if original is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        if original.status != TaskStatus.FAILED:
            raise ConflictError(
                "only failed tasks can be retried",
                details={"status": original.status.value},
            )
        if original.failure_category not in RETRYABLE_FAILURES:
            raise ConflictError(
                "task failure category is not retryable",
                details={"failure_category": original.failure_category},
            )
        if original.attempt >= original.max_attempts:
            raise ConflictError(
                "task has reached the maximum retry attempts",
                details={
                    "attempt": original.attempt,
                    "max_attempts": original.max_attempts,
                },
            )

        payload = dict(original.input_content)
        payload["task_id"] = new_id("task")
        options = dict(payload.get("options") or {})
        options.pop("idempotency_key", None)
        options["max_attempts"] = original.max_attempts
        payload["options"] = options
        request = AgentRequest.model_validate(payload)
        route_context = request.options.get("_routing", {})
        route_payload = dict(route_context) if isinstance(route_context, dict) else {}
        # Reuse the complete route contract so research retries remain typed.
        route_payload.update(
            {
                "agent_id": original.agent_id,
                "scene": request.scene.value,
                "course_id": original.course_id,
                "intent": original.intent,
                "route_status": original.route_status,
                "reason": f"retry preserves route from task {original.id}",
            }
        )
        new_task = await TaskCreationService(
            self.db, self.provider.provider_name
        ).create_queued(
            request,
            route=RouteDecision.model_validate(route_payload),
            parent_task_id=original.id,
            attempt=original.attempt + 1,
            existing_user_message_id=original.user_message_id,
        )
        await append_task_event(
            self.db,
            original.id,
            AgentEventType.TASK_RETRY_CREATED,
            agent_id=original.agent_id,
            data={"retry_task_id": new_task.id, "attempt": new_task.attempt},
        )
        await self.db.commit()
        return new_task

    async def cancel(self, task_id: str) -> TaskModel:
        task = await self.repository.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        if task.status in TERMINAL_STATUSES:
            raise ConflictError(
                "terminal tasks cannot be cancelled",
                details={"status": task.status.value},
            )
        if not task.cancellation_requested:
            task.cancellation_requested = True
            task.cancel_requested_at = datetime.now(UTC)
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.CANCEL_REQUESTED,
                agent_id=task.agent_id,
            )
        if task.status == TaskStatus.QUEUED:
            task.status = TaskStatus.CANCELLED
            now = datetime.now(UTC)
            task.completed_at = now
            task.updated_at = now
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.TASK_CANCELLED,
                agent_id=task.agent_id,
                data={"reason": "queued task cancelled"},
            )
            message = await ConversationMessageService(self.db).append_terminal_failure(
                task,
                status=MessageStatus.CANCELLED,
                reason="task cancelled",
            )
            task.assistant_message_id = message.id if message is not None else None
        await self.provider.cancel(task.id)
        if task.status in TERMINAL_STATUSES:
            async with self.db.begin_nested():
                await cleanup_evaluation_attachments(
                    self.db,
                    self._settings,
                    task_id=task.id,
                )
        await self.db.commit()
        return task

    async def pause(
        self, task_id: str, runtime_run_id: str | None = None
    ) -> TaskModel:
        task = await self.repository.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        if task.status in TERMINAL_STATUSES:
            raise ConflictError(
                "terminal tasks cannot be paused",
                details={"status": task.status.value},
            )
        runtime_repository = AgentRunRepository(self.db)
        runtime = await self._get_controlled_runtime(
            task.id,
            runtime_run_id,
            for_update=True,
        )
        if runtime is None:
            raise ConflictError("task has no Runtime run to control")
        if runtime.status not in {"created", "running", "queued"}:
            raise ConflictError(
                "Runtime status does not support pausing",
                details={"runtime_status": runtime.status},
            )
        await runtime_repository.request_control(runtime.id, "pause")
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.AGENT_PROGRESS,
            agent_id=task.agent_id,
            data={
                "stage_id": "runtime_control",
                "status": "pause_requested",
                "runtime_run_id": runtime.id,
            },
        )
        await self.db.commit()
        return task

    async def resume(
        self, task_id: str, runtime_run_id: str | None = None
    ) -> TaskModel:
        return await self._resume_runtime(
            task_id,
            allowed_statuses={"paused", "waiting_input"},
            action="resume",
            runtime_run_id=runtime_run_id,
        )

    async def approve(
        self, task_id: str, runtime_run_id: str | None = None
    ) -> TaskModel:
        return await self._resume_runtime(
            task_id,
            allowed_statuses={"waiting_approval"},
            action="approve",
            control_data={"approved": True},
            runtime_run_id=runtime_run_id,
        )

    async def submit_input(
        self, task_id: str, submission: RuntimeInputSubmission
    ) -> TaskModel:
        task = await self.repository.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        runtime_repository = AgentRunRepository(self.db)
        runtime = await runtime_repository.get_for_task(task.id, for_update=True)
        if runtime is None or runtime.status != "waiting_input":
            raise ConflictError(
                "Runtime status does not support user input",
                details={
                    "runtime_status": runtime.status if runtime else "missing"
                },
            )
        if (
            submission.expected_state_version is not None
            and runtime.state_version != submission.expected_state_version
        ):
            raise ConflictError(
                "Runtime state version has changed",
                details={
                    "expected_state_version": submission.expected_state_version,
                    "actual_state_version": runtime.state_version,
                },
            )
        control_data = dict(runtime.control_data or {})
        control_data["user_input"] = dict(submission.data)
        await runtime_repository.request_control(
            runtime.id,
            "",
            control_data=control_data,
        )
        task.status = TaskStatus.QUEUED
        task.updated_at = datetime.now(UTC)
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.AGENT_INPUT_SUBMITTED,
            agent_id=task.agent_id,
            data={
                "runtime_run_id": runtime.id,
                "state_version": runtime.state_version,
                "input_keys": sorted(submission.data),
            },
        )
        await self.db.commit()
        return task

    async def reconcile(
        self, task_id: str, submission: RuntimeReconciliationSubmission
    ) -> TaskModel:
        """Record an external outcome before a paused run is resumed.

        A node marked UNKNOWN must never be replayed implicitly: the external
        system may already have applied its side effect. This operation turns
        that uncertainty into an explicit, durable human acknowledgement.
        """

        task = await self.repository.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        if task.status in TERMINAL_STATUSES:
            raise ConflictError(
                "terminal tasks cannot be reconciled",
                details={"status": task.status.value},
            )
        runtime_repository = AgentRunRepository(self.db)
        runtime_model = await self._get_controlled_runtime(
            task.id,
            submission.runtime_run_id,
            for_update=True,
        )
        if runtime_model is None:
            raise ConflictError("task has no Runtime run to reconcile")
        if runtime_model.status != RuntimeRunStatus.PAUSED.value:
            raise ConflictError(
                "Runtime status does not support reconciliation",
                details={"runtime_status": runtime_model.status},
            )
        if (
            submission.expected_state_version is not None
            and runtime_model.state_version != submission.expected_state_version
        ):
            raise ConflictError(
                "Runtime state version has changed",
                details={
                    "expected_state_version": submission.expected_state_version,
                    "actual_state_version": runtime_model.state_version,
                },
            )
        run = await runtime_repository.restore(runtime_model.id)
        if run is None:
            raise ConflictError("Runtime checkpoint is missing")
        if run.state_version != runtime_model.state_version:
            raise ConflictError(
                "Runtime checkpoint is stale",
                details={
                    "checkpoint_state_version": run.state_version,
                    "runtime_state_version": runtime_model.state_version,
                },
            )
        node = run.nodes.get(submission.node_id)
        if (
            node is None
            or node.status != RuntimeNodeStatus.RUNNING
            or node.error_code != "in_flight_execution_requires_reconciliation"
        ):
            raise ConflictError(
                "Runtime node is not awaiting reconciliation",
                details={
                    "node_id": submission.node_id,
                    "node_status": node.status.value if node else "missing",
                    "error_code": node.error_code if node else "",
                },
            )
        if (
            submission.reconciliation_id is not None
            and submission.reconciliation_id != node.reconciliation_id
        ):
            raise ConflictError(
                "Runtime reconciliation identity has changed",
                details={
                    "expected_reconciliation_id": submission.reconciliation_id,
                    "actual_reconciliation_id": node.reconciliation_id,
                    "provider_trace_id": node.provider_trace_id,
                },
            )

        outcome = (
            RuntimeNodeStatus.SUCCEEDED
            if submission.outcome == "succeeded"
            else RuntimeNodeStatus.FAILED
        )
        observation = RuntimeObservation(
            node_id=submission.node_id,
            terminal_status=outcome,
            facts=dict(submission.facts),
            artifact_ids=list(submission.artifact_ids),
            evidence_ids=list(submission.evidence_ids),
            warnings=list(submission.warnings),
            errors=list(submission.errors),
        )
        RuntimeStateMachine.complete_node(
            run,
            submission.node_id,
            status=outcome,
            observation=observation,
            error_code=submission.error_code,
        )
        # Keep the run resumable even if the reconciled node was the final
        # node. The executor still needs one deterministic pass to produce its
        # final task presentation and terminal event.
        run.status = RuntimeRunStatus.PAUSED
        run.completed_at = None
        run.control_request = ""
        run.control_data = {}
        await runtime_repository.save_checkpoint(run)
        parent_runtime_id = ""
        if runtime_model.parent_run_id:
            parent_model = await runtime_repository.get(
                runtime_model.parent_run_id,
                for_update=True,
            )
            if parent_model is not None:
                parent_runtime_id = parent_model.id
                parent_control_data = dict(parent_model.control_data or {})
                if (
                    parent_control_data.get("suspended_child_run_id")
                    == runtime_model.id
                ):
                    parent_control_data.pop("suspended_child_run_id", None)
                    await runtime_repository.request_control(
                        parent_model.id,
                        "",
                        control_data=parent_control_data,
                    )
        task.status = TaskStatus.QUEUED
        task.updated_at = datetime.now(UTC)
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.AGENT_PROGRESS,
            agent_id=task.agent_id,
            data={
                "stage_id": "runtime_control",
                "status": "reconciled",
                "runtime_run_id": runtime_model.id,
                "parent_runtime_run_id": parent_runtime_id,
                "node_id": submission.node_id,
                "outcome": submission.outcome,
                "execution_key": node.execution_key,
                "reconciliation_id": node.reconciliation_id,
                "provider_trace_id": node.provider_trace_id,
                "state_version": run.state_version,
            },
        )
        await self.db.commit()
        return task

    async def _resume_runtime(
        self,
        task_id: str,
        *,
        allowed_statuses: set[str],
        action: str,
        control_data: dict[str, object] | None = None,
        runtime_run_id: str | None = None,
    ) -> TaskModel:
        task = await self.repository.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        runtime_repository = AgentRunRepository(self.db)
        requested_runtime = await self._get_controlled_runtime(
            task.id,
            runtime_run_id,
            for_update=True,
        )
        if requested_runtime is None:
            raise ConflictError("task has no Runtime run to control")
        runtime = requested_runtime
        if runtime_run_id is None:
            suspended_child_run_id = (runtime.control_data or {}).get(
                "suspended_child_run_id"
            )
            if isinstance(suspended_child_run_id, str) and suspended_child_run_id:
                child = await runtime_repository.get(
                    suspended_child_run_id,
                    for_update=True,
                )
                if (
                    child is not None
                    and child.parent_run_id == runtime.id
                    and child.status in allowed_statuses
                ):
                    runtime = child
        if runtime.status not in allowed_statuses:
            raise ConflictError(
                "Runtime status does not support this control",
                details={"runtime_status": runtime.status},
            )
        await runtime_repository.request_control(
            runtime.id,
            "",
            control_data=control_data,
        )
        parent_runtime_id = ""
        parent = None
        if runtime.parent_run_id:
            parent = await runtime_repository.get(
                runtime.parent_run_id,
                for_update=True,
            )
            if parent is not None:
                parent_runtime_id = parent.id
                parent_control_data = dict(parent.control_data or {})
                parent_control_data.pop("suspended_child_run_id", None)
                await runtime_repository.request_control(
                    parent.id,
                    "",
                    control_data=parent_control_data,
                )
        elif runtime.id != requested_runtime.id:
            parent_runtime_id = requested_runtime.id
        task.status = TaskStatus.QUEUED
        task.updated_at = datetime.now(UTC)
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.AGENT_PROGRESS,
            agent_id=task.agent_id,
            data={
                "stage_id": "runtime_control",
                "status": f"{action}_requested",
                "runtime_run_id": runtime.id,
                "parent_runtime_run_id": parent_runtime_id,
            },
        )
        await self.db.commit()
        return task

    async def _get_controlled_runtime(
        self,
        task_id: str,
        runtime_run_id: str | None,
        *,
        for_update: bool,
    ) -> AgentRunModel | None:
        repository = AgentRunRepository(self.db)
        if not runtime_run_id:
            return await repository.get_for_task(
                task_id,
                for_update=for_update,
            )
        runtime = await repository.get(runtime_run_id, for_update=for_update)
        if runtime is None or runtime.task_id != task_id:
            raise ConflictError(
                "Runtime run does not belong to this task",
                details={"runtime_run_id": runtime_run_id},
            )
        if runtime.run_kind not in {"runtime", "subagent"}:
            raise ConflictError(
                "Runtime run is not externally controllable",
                details={"run_kind": runtime.run_kind},
            )
        return runtime
