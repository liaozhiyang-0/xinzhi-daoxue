"""Durable execution boundary for typed Runtime sub-agent calls."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import AgentRequest, AgentResult
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeBatchHook,
    RuntimeController,
    RuntimeDecision,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeNodeSuspended,
    RuntimeObservation,
    RuntimeRunStatus,
)
from app.runtime.subagents import RuntimeSubagentDefinition


class RuntimeChildRunService:
    """Run a typed sub-agent as its own checkpointed Runtime Run.

    The service intentionally calls the existing internal-agent boundary. It
    gives that call a durable child Run and never routes the request through a
    second HTTP/provider entry point.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        internal_agents: Any,
        *,
        after_batch_hook: RuntimeBatchHook | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.internal_agents = internal_agents
        self.after_batch_hook = after_batch_hook

    async def execute(
        self,
        parent_run: AgentRun,
        parent_node: RuntimeNode,
        definition: RuntimeSubagentDefinition,
        request: AgentRequest,
        *,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        internal_agents: Any | None = None,
    ) -> AgentResult:
        result, _ = await self.execute_with_run(
            parent_run,
            parent_node,
            definition,
            request,
            event_hook=event_hook,
            internal_agents=internal_agents,
        )
        return result

    async def execute_with_run(
        self,
        parent_run: AgentRun,
        parent_node: RuntimeNode,
        definition: RuntimeSubagentDefinition,
        request: AgentRequest,
        *,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        internal_agents: Any | None = None,
    ) -> tuple[AgentResult, str]:
        child_run = await self._load_or_create(
            parent_run,
            parent_node,
            definition,
            request,
        )
        restored = self._result_from_run(child_run)
        if (
            restored is not None
            and child_run.status
            in {
                RuntimeRunStatus.COMPLETED,
                RuntimeRunStatus.FAILED,
                RuntimeRunStatus.CANCELLED,
            }
        ):
            self._absorb_child(parent_run, child_run)
            self._clear_parent_suspension(parent_run, child_run.run_id)
            return restored, child_run.run_id
        if child_run.status in {
            RuntimeRunStatus.COMPLETED,
            RuntimeRunStatus.FAILED,
            RuntimeRunStatus.CANCELLED,
        }:
            raise RuntimeNodeError("subagent_child_result_missing")

        registry = RuntimeHandlerRegistry()
        agent_service = (
            internal_agents if internal_agents is not None else self.internal_agents
        )

        async def invoke(
            current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            result = await agent_service.run(
                definition.target_agent_id,
                request,
                None,
            )
            return RuntimeObservation(
                node_id=node.node_id,
                terminal_status=(
                    RuntimeNodeStatus.PARTIAL
                    if result.status.value == "failed"
                    else RuntimeNodeStatus.SUCCEEDED
                ),
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={
                    "subagent_id": definition.subagent_id,
                    "target_agent_id": definition.target_agent_id,
                    "child_run_id": current.run_id,
                    "parent_run_id": current.parent_run_id,
                    "result_status": result.status.value,
                    "structured_result": result.structured_result,
                    "answer": result.answer,
                    "result_payload": result.model_dump(mode="json"),
                },
                warnings=list(result.warnings[:8]),
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="subagent.child.invoke",
                kind="provider",
                version=definition.version,
                requires_approval=definition.requires_approval,
                side_effecting=definition.side_effecting,
                replay_safe=definition.replay_safe,
                max_timeout_ms=definition.max_timeout_ms,
            ),
            invoke,
        )
        executor = PlanExecutor(
            registry,
            checkpoint_hook=self._checkpoint,
            event_hook=event_hook,
            after_batch_hook=self.after_batch_hook,
        )
        child_controller = RuntimeController(
            executor,
            self._decide_child,
            checkpoint_hook=self._checkpoint,
            control_provider=lambda current: self._child_control(
                current, parent_run.run_id
            ),
        )
        child_run = await child_controller.run(child_run)
        if child_run.status in {
            RuntimeRunStatus.WAITING_INPUT,
            RuntimeRunStatus.WAITING_APPROVAL,
            RuntimeRunStatus.PAUSED,
        }:
            self._mark_parent_suspension(parent_run, child_run)
            if event_hook is not None:
                await _resolve_event(
                    event_hook("node_suspended", child_run, "subagent.execute")
                )
            raise RuntimeNodeSuspended(child_run.status)
        if child_run.status in {
            RuntimeRunStatus.COMPLETED,
            RuntimeRunStatus.FAILED,
            RuntimeRunStatus.CANCELLED,
        }:
            self._absorb_child(parent_run, child_run)
            self._clear_parent_suspension(parent_run, child_run.run_id)
        result = self._result_from_run(child_run)
        if result is None:
            raise RuntimeNodeError("subagent_child_result_missing")
        return result, child_run.run_id

    async def _load_or_create(
        self,
        parent_run: AgentRun,
        parent_node: RuntimeNode,
        definition: RuntimeSubagentDefinition,
        request: AgentRequest,
    ) -> AgentRun:
        async with self.session_factory() as db:
            repository = AgentRunRepository(db)
            model = await repository.get_child_for_node(
                parent_run.run_id,
                parent_node.node_id,
                for_update=True,
            )
            if model is not None:
                restored = await repository.restore(model.id)
                if restored is not None:
                    restored.control_request = model.control_request
                    restored.control_data = dict(model.control_data or {})
                    return restored
            child_run = AgentRun(
                run_id=uuid4().hex,
                task_id=parent_run.task_id,
                run_kind="subagent",
                parent_run_id=parent_run.run_id,
                parent_node_id=parent_node.node_id,
                goal=f"subagent:{definition.subagent_id}",
                budget=parent_run.budget.allocate_child(),
                plan=AgentRunPlan(
                    plan_id=f"subagent-runtime:{definition.subagent_id}",
                    version=definition.version,
                    goal=f"subagent:{definition.target_agent_id}",
                    nodes=[
                        RuntimeNode(
                            node_id="subagent.execute",
                            node_type="provider",
                            handler_id="subagent.child.invoke",
                            target_id=definition.target_agent_id,
                            timeout_ms=definition.max_timeout_ms,
                        )
                    ],
                ),
                request_snapshot=request.model_dump(mode="json"),
            )
            await repository.create(
                child_run,
                agent_id=definition.target_agent_id,
                provider="internal",
                run_kind="subagent",
                parent_run_id=parent_run.run_id,
                parent_node_id=parent_node.node_id,
            )
            await db.commit()
            return child_run

    async def _checkpoint(self, run: AgentRun) -> None:
        async with self.session_factory() as db:
            await AgentRunRepository(db).save_checkpoint(run)
            await db.commit()

    async def _child_control(
        self, run: AgentRun, parent_run_id: str
    ) -> RuntimeDecision | None:
        async with self.session_factory() as db:
            repository = AgentRunRepository(db)
            child_model = await repository.get(run.run_id)
            parent_model = await repository.get(parent_run_id)
        for model, reason in (
            (child_model, "child_pause_requested"),
            (parent_model, "parent_pause_requested"),
        ):
            if model is not None and model.control_request == "pause":
                return RuntimeDecision(
                    action=DecisionAction.PAUSE,
                    reason_codes=[reason],
                )
        return None

    @staticmethod
    def _decide_child(run: AgentRun) -> RuntimeDecision:
        pending = [
            node_id
            for node_id, state in run.nodes.items()
            if state.status.value in {"pending", "ready", "running"}
        ]
        if pending:
            return RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=pending,
                reason_codes=["child_node_ready"],
            )
        return RuntimeDecision(
            action=DecisionAction.FINISH,
            reason_codes=["child_run_terminal"],
        )

    @staticmethod
    def _absorb_child(parent_run: AgentRun, child_run: AgentRun) -> None:
        try:
            parent_run.budget.absorb_child(child_run.run_id, child_run.budget)
        except ValueError as exc:
            raise RuntimeNodeError(str(exc)) from exc

    @staticmethod
    def _mark_parent_suspension(
        parent_run: AgentRun, child_run: AgentRun
    ) -> None:
        control_data = dict(parent_run.control_data)
        control_data["suspended_child_run_id"] = child_run.run_id
        parent_run.control_data = control_data

    @staticmethod
    def _clear_parent_suspension(parent_run: AgentRun, child_run_id: str) -> None:
        if parent_run.control_data.get("suspended_child_run_id") != child_run_id:
            return
        control_data = dict(parent_run.control_data)
        control_data.pop("suspended_child_run_id", None)
        parent_run.control_data = control_data

    @staticmethod
    def _result_from_run(run: AgentRun) -> AgentResult | None:
        for node in run.plan.nodes:
            observation = run.nodes[node.node_id].observation
            if observation is None:
                continue
            payload = observation.facts.get("result_payload")
            if isinstance(payload, dict):
                return AgentResult.model_validate(payload)
        return None


async def _resolve_event(value: Any) -> None:
    if inspect.isawaitable(value):
        await value
