from __future__ import annotations

from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentCheckpointModel,
    AgentRunModel,
    AgentRunNodeModel,
    TaskEventModel,
)
from app.runtime import AgentRun, RuntimeNodeStatus


class RuntimeConcurrencyError(RuntimeError):
    """Raised when a worker tries to overwrite a newer runtime snapshot."""


class AgentRunRepository:
    """Persist and restore AgentRun snapshots without executing any handlers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        run: AgentRun,
        *,
        agent_id: str,
        provider: str,
        workflow_version: str = "1.0.0",
        trace_id: str | None = None,
        run_kind: str = "runtime",
        parent_run_id: str | None = None,
        parent_node_id: str | None = None,
    ) -> AgentRunModel:
        run.run_kind = run_kind
        run.parent_run_id = parent_run_id or ""
        run.parent_node_id = parent_node_id or ""
        model = AgentRunModel(
            id=run.run_id,
            task_id=run.task_id,
            agent_id=agent_id,
            run_kind=run_kind,
            parent_run_id=parent_run_id or "",
            parent_node_id=parent_node_id or "",
            plan_id=run.plan.plan_id,
            plan_version=run.plan.version,
            iteration=run.iteration,
            budget_data=run.budget.model_dump(mode="json"),
            state_version=run.state_version,
            agent_version=run.plan.version,
            provider=provider,
            workflow_version=workflow_version,
            status=run.status.value,
            trace_id=trace_id,
            metrics_data={},
            control_request=run.control_request,
            control_data=run.control_data,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        self.session.add(model)
        for node in run.plan.nodes:
            self.session.add(self._node_model(run, node.node_id))
        await self.session.flush()
        await self._add_checkpoint(
            run,
            sequence=1,
            event_sequence=await self._current_event_sequence(run.task_id),
        )
        return model

    async def get(
        self, run_id: str, *, for_update: bool = False
    ) -> AgentRunModel | None:
        query = select(AgentRunModel).where(AgentRunModel.id == run_id)
        if for_update:
            query = query.with_for_update()
        return cast(AgentRunModel | None, await self.session.scalar(query))

    async def get_for_task(
        self,
        task_id: str,
        *,
        run_kind: str = "runtime",
        for_update: bool = False,
    ) -> AgentRunModel | None:
        query = (
            select(AgentRunModel)
            .where(
                AgentRunModel.task_id == task_id,
                AgentRunModel.run_kind == run_kind,
            )
            .order_by(AgentRunModel.created_at.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        return cast(AgentRunModel | None, await self.session.scalar(query))

    async def get_child_for_node(
        self,
        parent_run_id: str,
        parent_node_id: str,
        *,
        for_update: bool = False,
    ) -> AgentRunModel | None:
        """Return the durable child Run for one parent node, if it exists."""

        query = (
            select(AgentRunModel)
            .where(
                AgentRunModel.parent_run_id == parent_run_id,
                AgentRunModel.parent_node_id == parent_node_id,
                AgentRunModel.run_kind == "subagent",
            )
            .order_by(AgentRunModel.created_at.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        return cast(AgentRunModel | None, await self.session.scalar(query))

    async def list_children(
        self, parent_run_id: str, *, run_kind: str = "subagent"
    ) -> list[AgentRunModel]:
        result = await self.session.scalars(
            select(AgentRunModel)
            .where(
                AgentRunModel.parent_run_id == parent_run_id,
                AgentRunModel.run_kind == run_kind,
            )
            .order_by(AgentRunModel.created_at)
        )
        return list(result.all())

    async def save_checkpoint(
        self,
        run: AgentRun,
        *,
        event_sequence: int | None = None,
        expected_state_version: int | None = None,
        provider: str | None = None,
        metrics_data: dict[str, object] | None = None,
        latency_ms: int | None = None,
        trace_id: str | None = None,
        terminal_reason: str | None = None,
    ) -> AgentCheckpointModel:
        model = await self.get(run.run_id, for_update=True)
        if model is None:
            raise ValueError(f"runtime run does not exist: {run.run_id}")
        expected = expected_state_version or run.state_version
        if model.state_version != expected:
            raise RuntimeConcurrencyError(
                f"runtime state version conflict: expected {expected}, "
                f"stored {model.state_version}"
            )

        next_version = expected + 1
        run.state_version = next_version
        model.iteration = run.iteration
        model.run_kind = run.run_kind
        model.parent_run_id = run.parent_run_id
        model.parent_node_id = run.parent_node_id
        model.plan_id = run.plan.plan_id
        model.plan_version = run.plan.version
        model.agent_version = run.plan.version
        model.budget_data = run.budget.model_dump(mode="json")
        model.status = run.status.value
        model.control_request = run.control_request
        model.control_data = run.control_data
        model.state_version = next_version
        model.started_at = run.started_at
        model.completed_at = run.completed_at
        if provider is not None:
            model.provider = provider
        if metrics_data is not None:
            model.metrics_data = metrics_data
        if latency_ms is not None:
            model.latency_ms = latency_ms
        if trace_id is not None:
            model.trace_id = trace_id
        if terminal_reason is not None:
            model.terminal_reason = terminal_reason
        else:
            model.terminal_reason = (
                run.last_decision.reason_codes[0]
                if run.last_decision and run.last_decision.reason_codes
                else ""
            )
        stored_nodes = list(
            (
                await self.session.scalars(
                    select(AgentRunNodeModel).where(
                        AgentRunNodeModel.run_id == run.run_id
                    )
                )
            ).all()
        )
        current_node_ids = {node.node_id for node in run.plan.nodes}
        for node_model in stored_nodes:
            if node_model.node_id not in current_node_ids:
                await self.session.delete(node_model)
        stored_by_id = {node.node_id: node for node in stored_nodes}
        for node in run.plan.nodes:
            existing_node = stored_by_id.get(node.node_id)
            if existing_node is None:
                self.session.add(self._node_model(run, node.node_id))
                continue
            self._update_node(existing_node, run, node.node_id)
        if event_sequence is None:
            event_sequence = await self._current_event_sequence(run.task_id)
        checkpoint = await self._add_checkpoint(
            run,
            sequence=await self._next_checkpoint_sequence(run.run_id),
            event_sequence=event_sequence,
        )
        await self.session.flush()
        return checkpoint

    async def request_control(
        self,
        run_id: str,
        control_request: str,
        *,
        control_data: dict[str, object] | None = None,
    ) -> AgentRunModel:
        model = await self.get(run_id, for_update=True)
        if model is None:
            raise ValueError(f"runtime run does not exist: {run_id}")
        model.control_request = control_request
        model.control_data = control_data or {}
        await self.session.flush()
        return model

    async def clear_control(self, run_id: str) -> AgentRunModel:
        return await self.request_control(run_id, "")

    async def restore(self, run_id: str) -> AgentRun | None:
        checkpoint = await self.session.scalar(
            select(AgentCheckpointModel)
            .where(AgentCheckpointModel.run_id == run_id)
            .order_by(AgentCheckpointModel.sequence.desc())
            .limit(1)
        )
        if checkpoint is None:
            return None
        run = AgentRun.model_validate(checkpoint.state_data)
        model = await self.get(run_id)
        if model is not None:
            run.run_kind = model.run_kind
            run.parent_run_id = model.parent_run_id
            run.parent_node_id = model.parent_node_id
        return run

    async def list_checkpoints(self, run_id: str) -> list[AgentCheckpointModel]:
        result = await self.session.scalars(
            select(AgentCheckpointModel)
            .where(AgentCheckpointModel.run_id == run_id)
            .order_by(AgentCheckpointModel.sequence)
        )
        return list(result.all())

    async def _add_checkpoint(
        self, run: AgentRun, *, sequence: int, event_sequence: int
    ) -> AgentCheckpointModel:
        checkpoint = AgentCheckpointModel(
            run_id=run.run_id,
            sequence=sequence,
            state_version=run.state_version,
            status=run.status.value,
            state_data=run.model_dump(mode="json"),
            event_sequence=event_sequence,
        )
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint

    async def _next_checkpoint_sequence(self, run_id: str) -> int:
        value = await self.session.scalar(
            select(func.max(AgentCheckpointModel.sequence)).where(
                AgentCheckpointModel.run_id == run_id
            )
        )
        return int(value or 0) + 1

    async def _current_event_sequence(self, task_id: str) -> int:
        """Return the latest committed Task event visible to this session.

        Runtime checkpoints and Task events are stored separately, so keeping
        this correlation value on every checkpoint is what makes a restored
        Runtime trace auditable.  The query is intentionally read-only and
        uses the current transaction, which also sees events flushed by the
        caller before a checkpoint is saved.
        """

        value = await self.session.scalar(
            select(func.max(TaskEventModel.sequence)).where(
                TaskEventModel.task_id == task_id
            )
        )
        return int(value or 0)

    async def _get_node(
        self, run_id: str, node_id: str
    ) -> AgentRunNodeModel | None:
        return cast(
            AgentRunNodeModel | None,
            await self.session.scalar(
                select(AgentRunNodeModel).where(
                    AgentRunNodeModel.run_id == run_id,
                    AgentRunNodeModel.node_id == node_id,
                )
            ),
        )

    @staticmethod
    def _node_model(run: AgentRun, node_id: str) -> AgentRunNodeModel:
        node = next(item for item in run.plan.nodes if item.node_id == node_id)
        state = run.nodes[node_id]
        observation = state.observation
        observation_data = (
            observation.model_dump(mode="json") if observation else {}
        )
        observation_data["_runtime_effect"] = {
            "execution_key": state.execution_key,
            "reconciliation_id": state.reconciliation_id,
            "provider_trace_id": state.provider_trace_id,
        }
        return AgentRunNodeModel(
            run_id=run.run_id,
            node_id=node.node_id,
            node_type=node.node_type,
            handler_id=node.handler_id,
            target_id=node.target_id,
            execution_key=state.execution_key,
            effect_status=state.effect_status.value,
            status=state.status.value,
            attempt=state.attempt,
            max_retries=node.max_retries,
            dependencies=node.depends_on,
            input_artifact_ids=node.input_artifact_ids,
            output_artifact_ids=observation.artifact_ids if observation else [],
            observation_data=observation_data,
            error_code=state.error_code,
            started_at=state.started_at,
            completed_at=state.completed_at,
        )

    @staticmethod
    def _update_node(model: AgentRunNodeModel, run: AgentRun, node_id: str) -> None:
        state = run.nodes[node_id]
        observation = state.observation
        node = next(item for item in run.plan.nodes if item.node_id == node_id)
        model.target_id = node.target_id
        model.execution_key = state.execution_key
        model.effect_status = state.effect_status.value
        model.status = state.status.value
        model.attempt = state.attempt
        model.output_artifact_ids = observation.artifact_ids if observation else []
        observation_data = (
            observation.model_dump(mode="json") if observation else {}
        )
        observation_data["_runtime_effect"] = {
            "execution_key": state.execution_key,
            "reconciliation_id": state.reconciliation_id,
            "provider_trace_id": state.provider_trace_id,
        }
        model.observation_data = observation_data
        model.error_code = state.error_code
        model.started_at = state.started_at
        model.completed_at = state.completed_at
        if state.status in {
            RuntimeNodeStatus.SUCCEEDED,
            RuntimeNodeStatus.PARTIAL,
            RuntimeNodeStatus.FAILED,
            RuntimeNodeStatus.SKIPPED,
            RuntimeNodeStatus.BLOCKED,
        } and state.completed_at is not None:
            model.updated_at = state.completed_at
