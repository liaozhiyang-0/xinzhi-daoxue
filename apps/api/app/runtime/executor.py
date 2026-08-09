from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Collection, Mapping
from typing import Any

from app.runtime.contracts import (
    AgentRun,
    DecisionAction,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
)
from app.runtime.handler_registry import (
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeHandlerRegistryError,
    RuntimeNodeHandler,
)
from app.runtime.state_machine import RuntimeStateMachine

CheckpointHook = Callable[[AgentRun], Any]
RuntimeEventHook = Callable[[str, AgentRun, str], Any]
RuntimeBatchHook = Callable[[AgentRun, Collection[str]], Any]


class RuntimeNodeError(RuntimeError):
    """Optional structured failure raised by a node handler."""

    def __init__(self, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code


class RuntimeNodeSuspended(RuntimeError):
    """Signal that a nested node paused its parent execution boundary."""

    def __init__(self, status: RuntimeRunStatus) -> None:
        super().__init__(f"runtime node suspended: {status.value}")
        self.status = status


class PlanExecutor:
    """Execute a validated plan through registered, bounded node handlers.

    The executor is deliberately storage-agnostic. A checkpoint hook receives
    the serializable AgentRun after state changes; the durable repository will
    be connected before this executor replaces the production TaskRunner path.
    """

    def __init__(
        self,
        handlers: Mapping[str, RuntimeNodeHandler] | RuntimeHandlerRegistry,
        *,
        checkpoint_hook: CheckpointHook | None = None,
        event_hook: RuntimeEventHook | None = None,
        after_batch_hook: RuntimeBatchHook | None = None,
    ) -> None:
        self.handlers = handlers
        self.checkpoint_hook = checkpoint_hook
        self.event_hook = event_hook
        self.after_batch_hook = after_batch_hook

    async def execute(
        self,
        run: AgentRun,
        *,
        node_ids: Collection[str] | None = None,
    ) -> AgentRun:
        selected = set(node_ids) if node_ids is not None else None
        if not await self._recover_inflight(run, selected):
            return run
        RuntimeStateMachine.mark_ready(run, only_node_ids=selected)
        await self._block_unreachable(run)
        await self._checkpoint(run)
        while True:
            ready = [
                node_id
                for node_id, state in run.nodes.items()
                if state.status == RuntimeNodeStatus.READY
                and (selected is None or node_id in selected)
            ]
            if not ready:
                if self._is_terminal(run):
                    return run
                if selected is not None:
                    return run
                raise RuntimeError("runtime plan has no executable ready node")

            if isinstance(self.handlers, RuntimeHandlerRegistry):
                for node_id in ready:
                    node = self._node(run, node_id)
                    try:
                        descriptor = self.handlers.descriptor(node.handler_id)
                    except RuntimeHandlerRegistryError:
                        # Let the normal execution path report the precise
                        # registration error for this node.
                        continue
                    if not descriptor.requires_approval:
                        continue
                    if run.control_data.get("approved") is not True:
                        RuntimeStateMachine.apply_decision(
                            run,
                            RuntimeDecision(
                                action=DecisionAction.REQUEST_APPROVAL,
                                approval_scope=node.handler_id,
                                reason_codes=["handler_requires_approval"],
                            ),
                        )
                        await self._emit("approval_required", run, node_id)
                        await self._checkpoint(run)
                        return run
                    # Approval is a one-shot control signal. Keep the
                    # checkpointed request and node inputs available to the
                    # approved node and any downstream nodes.
                    control_data = dict(run.control_data)
                    control_data.pop("approved", None)
                    run.control_data = control_data
                    break

            batch = ready[: run.plan.max_parallelism]
            executable: list[str] = []
            pre_results: dict[str, RuntimeObservation | BaseException] = {}
            for node_id in batch:
                RuntimeStateMachine.start_node(run, node_id)
                try:
                    # Reserve before the durable RUNNING checkpoint. If the
                    # process is lost after the external call, recovery still
                    # sees the consumed budget and will not undercount it.
                    run.budget.reserve(self._node(run, node_id).node_type)
                except ValueError as exc:
                    pre_results[node_id] = RuntimeNodeError(str(exc))
                else:
                    executable.append(node_id)
                await self._emit("node_started", run, node_id)
            await self._checkpoint(run)

            results = pre_results
            if executable:
                results.update(await self._execute_batch(run, executable))
                # This hook is intentionally after handler completion but
                # before node completion is checkpointed. Tests and worker
                # fault injection can therefore model a process loss after
                # an external effect may have happened, leaving the durable
                # node RUNNING.
                if self.after_batch_hook is not None:
                    hook_result = self.after_batch_hook(run, executable)
                    if inspect.isawaitable(hook_result):
                        await hook_result
            for node_id, result in results.items():
                if isinstance(result, BaseException):
                    await self._handle_failure(run, node_id, result)
                    continue
                RuntimeStateMachine.complete_node(
                    run,
                    node_id,
                    status=result.terminal_status,
                    observation=result,
                )
                await self._emit("node_completed", run, node_id)
            await self._block_unreachable(run)
            RuntimeStateMachine.mark_ready(run)
            await self._checkpoint(run)

    async def _execute_batch(
        self, run: AgentRun, node_ids: list[str]
    ) -> dict[str, RuntimeObservation | BaseException]:
        async def execute_one(node_id: str) -> RuntimeObservation:
            node = self._node(run, node_id)
            try:
                handler = (
                    self.handlers.resolve(node)
                    if isinstance(self.handlers, RuntimeHandlerRegistry)
                    else self.handlers.get(node.handler_id)
                )
            except RuntimeHandlerRegistryError as exc:
                raise RuntimeNodeError(exc.error_code, str(exc)) from exc
            if handler is None:
                raise RuntimeNodeError(
                    "handler_not_registered",
                    f"未注册 Runtime handler: {node.handler_id}",
                )
            async with asyncio.timeout(node.timeout_ms / 1000):
                result = handler(run, node)
                if inspect.isawaitable(result):
                    result = await result
            if not isinstance(result, RuntimeObservation):
                raise RuntimeNodeError(
                    "invalid_observation",
                    "Runtime handler must return RuntimeObservation",
                )
            if result.node_id != node_id:
                raise RuntimeNodeError(
                    "observation_node_mismatch", "Runtime observation node_id 不匹配"
                )
            return result

        gathered = await _gather_with_exceptions(
            *(execute_one(node_id) for node_id in node_ids)
        )
        return dict(zip(node_ids, gathered, strict=True))

    async def _handle_failure(
        self, run: AgentRun, node_id: str, error: BaseException
    ) -> None:
        node = self._node(run, node_id)
        if isinstance(error, RuntimeNodeSuspended):
            state = run.nodes[node_id]
            state.status = RuntimeNodeStatus.READY
            state.effect_status = RuntimeEffectStatus.UNKNOWN
            state.error_code = "nested_run_suspended"
            run.status = error.status
            await self._emit("node_suspended", run, node_id)
            return
        error_code = (
            error.error_code
            if isinstance(error, RuntimeNodeError)
            else type(error).__name__
        )
        state = run.nodes[node_id]
        descriptor = self._descriptor(node.handler_id)
        if (
            descriptor is not None
            and descriptor.side_effecting
            and not descriptor.replay_safe
        ):
            error_code = "side_effect_retry_not_safe"
            RuntimeStateMachine.complete_node(
                run,
                node_id,
                status=RuntimeNodeStatus.FAILED,
                error_code=error_code,
            )
            await self._emit("node_failed", run, node_id)
            return
        if state.attempt <= node.max_retries:
            RuntimeStateMachine.retry_node(
                run, node_id, error_code=error_code
            )
            await self._emit("node_retrying", run, node_id)
            return
        RuntimeStateMachine.complete_node(
            run,
            node_id,
            status=RuntimeNodeStatus.FAILED,
            error_code=error_code,
        )
        await self._emit("node_failed", run, node_id)

    async def _recover_inflight(
        self, run: AgentRun, selected: set[str] | None
    ) -> bool:
        """Recover a checkpointed RUNNING node without blind side effects."""

        inflight = [
            node_id
            for node_id, state in run.nodes.items()
            if state.status == RuntimeNodeStatus.RUNNING
            and (selected is None or node_id in selected)
        ]
        if not inflight:
            return True
        for node_id in inflight:
            node = self._node(run, node_id)
            state = run.nodes[node_id]
            # Upgrade pre-identity checkpoints deterministically before any
            # recovery decision. This keeps old Runs auditable without
            # changing their execution key or replaying the side effect.
            if not state.execution_key:
                state.execution_key = f"{run.run_id}:{node_id}"
            if not state.reconciliation_id:
                state.reconciliation_id = f"runtime:{run.run_id}:{node_id}"
            descriptor = self._descriptor(node.handler_id)
            if descriptor is not None and descriptor.replay_safe:
                state.status = RuntimeNodeStatus.READY
                state.effect_status = RuntimeEffectStatus.UNKNOWN
                await self._emit("node_recovered", run, node_id)
                continue
            state.effect_status = RuntimeEffectStatus.UNKNOWN
            state.error_code = "in_flight_execution_requires_reconciliation"
            RuntimeStateMachine.apply_decision(
                run,
                RuntimeDecision(
                    action=DecisionAction.PAUSE,
                    reason_codes=["in_flight_execution_requires_reconciliation"],
                ),
            )
            await self._emit("node_recovery_required", run, node_id)
            await self._checkpoint(run)
            return False
        run.status = RuntimeRunStatus.RUNNING
        return True

    def _descriptor(self, handler_id: str) -> RuntimeHandlerDescriptor | None:
        if not isinstance(self.handlers, RuntimeHandlerRegistry):
            return None
        try:
            return self.handlers.descriptor(handler_id)
        except RuntimeHandlerRegistryError:
            return None

    def _node(self, run: AgentRun, node_id: str) -> RuntimeNode:
        for node in run.plan.nodes:
            if node.node_id == node_id:
                return node
        raise RuntimeError(f"runtime node missing from plan: {node_id}")

    @staticmethod
    def _is_terminal(run: AgentRun) -> bool:
        return all(
            state.status in RuntimeStateMachine.TERMINAL_NODE_STATUSES
            for state in run.nodes.values()
        )

    async def _checkpoint(self, run: AgentRun) -> None:
        if self.checkpoint_hook is None:
            return
        result = self.checkpoint_hook(run)
        if inspect.isawaitable(result):
            await result

    async def _emit(self, event: str, run: AgentRun, node_id: str) -> None:
        if self.event_hook is None:
            return
        result = self.event_hook(event, run, node_id)
        if inspect.isawaitable(result):
            await result

    async def _block_unreachable(self, run: AgentRun) -> None:
        blocked_before = {
            node_id
            for node_id, state in run.nodes.items()
            if state.status == RuntimeNodeStatus.BLOCKED
        }
        RuntimeStateMachine.block_unreachable_nodes(run)
        for node_id, state in run.nodes.items():
            if (
                state.status == RuntimeNodeStatus.BLOCKED
                and node_id not in blocked_before
            ):
                await self._emit("node_blocked", run, node_id)


async def _gather_with_exceptions(
    *awaitables: Awaitable[RuntimeObservation],
) -> list[RuntimeObservation | BaseException]:
    results = await asyncio.gather(*awaitables, return_exceptions=True)
    return list(results)
