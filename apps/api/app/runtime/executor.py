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
    RuntimeNodeState,
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

_SAFE_REPLAY_BUDGET_RESERVATION = "replay_pending"


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
    the serializable AgentRun after state changes; production persistence is
    connected through RuntimePersistenceHooks.
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
        recovered_replays = await self._recover_inflight(run, selected)
        if recovered_replays is None:
            return run
        before_prepare = self._checkpoint_fingerprint(run)
        RuntimeStateMachine.mark_ready(run, only_node_ids=selected)
        await self._block_unreachable(run)
        if self._checkpoint_fingerprint(run) != before_prepare:
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
                gated_ready = await self._gate_approval(run, ready)
                if gated_ready is None:
                    return run
                ready = gated_ready

            batch = ready[: run.plan.max_parallelism]
            executable: list[str] = []
            pre_results: dict[str, RuntimeObservation | BaseException] = {}
            for node_id in batch:
                RuntimeStateMachine.start_node(run, node_id)
                state = self._node_state(run, node_id)
                if (
                    node_id in recovered_replays
                    or state.budget_reservation
                    == _SAFE_REPLAY_BUDGET_RESERVATION
                ):
                    # The original attempt reserved its budget before the
                    # RUNNING checkpoint. Safe recovery is a replay of that
                    # same attempt, so do not charge the node a second time.
                    recovered_replays.discard(node_id)
                    state.budget_reservation = ""
                    executable.append(node_id)
                else:
                    try:
                        # Reserve before the durable RUNNING checkpoint. If
                        # the process is lost after the external call,
                        # recovery still sees the consumed budget and will
                        # not undercount it.
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
            if node.skill_id:
                result = result.model_copy(
                    update={
                        "skill_id": node.skill_id,
                        "skill_version": node.skill_version,
                        "skill_binding_id": node.skill_binding_id,
                    }
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
            else str(getattr(error, "code", "")) or type(error).__name__
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
    ) -> set[str] | None:
        """Recover a checkpointed RUNNING node without blind side effects."""

        inflight = [
            node_id
            for node_id, state in run.nodes.items()
            if state.status == RuntimeNodeStatus.RUNNING
            and (selected is None or node_id in selected)
        ]
        if not inflight:
            return set()
        recovered_replays: set[str] = set()
        reconciliation_required = False
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
                # Persist the reservation across a mixed-batch pause. The
                # next worker may not be the one currently executing this
                # method, so a local replay set alone is insufficient.
                state.budget_reservation = _SAFE_REPLAY_BUDGET_RESERVATION
                recovered_replays.add(node_id)
                await self._emit("node_recovered", run, node_id)
                continue
            state.effect_status = RuntimeEffectStatus.UNKNOWN
            state.error_code = "in_flight_execution_requires_reconciliation"
            reconciliation_required = True
            await self._emit("node_recovery_required", run, node_id)
        if reconciliation_required:
            RuntimeStateMachine.apply_decision(
                run,
                RuntimeDecision(
                    action=DecisionAction.PAUSE,
                    reason_codes=["in_flight_execution_requires_reconciliation"],
                ),
            )
            await self._checkpoint(run)
            return None
        run.status = RuntimeRunStatus.RUNNING
        return recovered_replays

    def _descriptor(self, handler_id: str) -> RuntimeHandlerDescriptor | None:
        if not isinstance(self.handlers, RuntimeHandlerRegistry):
            return None
        try:
            return self.handlers.descriptor(handler_id)
        except RuntimeHandlerRegistryError:
            return None

    async def _gate_approval(
        self, run: AgentRun, ready: list[str]
    ) -> list[str] | None:
        """Apply one explicit approval to exactly one ready capability.

        A Runtime plan may intentionally schedule independent capabilities in
        parallel.  An approval for one side-effecting handler must never also
        authorize another ready handler in that batch.  The control service
        stores the approved handler ID, and this executor consumes that grant
        before dispatching the selected node.  Older checkpoints that predate
        ``approved_scope`` recover their scope from the recorded decision.
        """

        descriptors: dict[str, RuntimeHandlerDescriptor] = {}
        approval_node_ids: list[str] = []
        for node_id in ready:
            node = self._node(run, node_id)
            descriptor = self._descriptor(node.handler_id)
            if descriptor is None:
                # Let the normal execution path report the precise
                # registration error for this node.
                continue
            descriptors[node_id] = descriptor
            if descriptor.requires_approval:
                approval_node_ids.append(node_id)

        if not approval_node_ids:
            return ready

        approved_scope = self._approved_scope(run)
        approved_node_id = next(
            (
                node_id
                for node_id in approval_node_ids
                if descriptors[node_id].handler_id == approved_scope
            ),
            None,
        )
        if approved_node_id is not None:
            # Approval is one-shot and scope-bound.  Keep unrelated read-only
            # work eligible for this batch, but leave every other privileged
            # node READY for its own approval round.
            control_data = dict(run.control_data)
            control_data.pop("approved", None)
            control_data.pop("approved_scope", None)
            run.control_data = control_data
            return [
                approved_node_id,
                *[
                    node_id
                    for node_id in ready
                    if node_id != approved_node_id
                    and (
                        node_id not in descriptors
                        or not descriptors[node_id].requires_approval
                    )
                ],
            ]

        # A grant that no longer maps to a ready node (for example after a
        # plan replacement) cannot be repurposed.  Replace it with a fresh,
        # explicit request for the first deterministic ready handler.
        if run.control_data.get("approved") is True:
            control_data = dict(run.control_data)
            control_data.pop("approved", None)
            control_data.pop("approved_scope", None)
            run.control_data = control_data
        node_id = approval_node_ids[0]
        RuntimeStateMachine.apply_decision(
            run,
            RuntimeDecision(
                action=DecisionAction.REQUEST_APPROVAL,
                approval_scope=descriptors[node_id].handler_id,
                reason_codes=["handler_requires_approval"],
            ),
        )
        await self._emit("approval_required", run, node_id)
        await self._checkpoint(run)
        return None

    @staticmethod
    def _approved_scope(run: AgentRun) -> str:
        """Return the durable scope attached to a one-shot approval grant."""

        if run.control_data.get("approved") is not True:
            return ""
        value = run.control_data.get("approved_scope")
        if isinstance(value, str) and value.strip():
            return value.strip()
        # ``approved_scope`` was added after the initial approval control
        # contract. Existing waiting checkpoints retain the decision scope.
        for decision in reversed(run.decision_history):
            if decision.action == DecisionAction.REQUEST_APPROVAL:
                return decision.approval_scope
        return ""

    def _node(self, run: AgentRun, node_id: str) -> RuntimeNode:
        for node in run.plan.nodes:
            if node.node_id == node_id:
                return node
        raise RuntimeError(f"runtime node missing from plan: {node_id}")

    @staticmethod
    def _node_state(run: AgentRun, node_id: str) -> RuntimeNodeState:
        try:
            return run.nodes[node_id]
        except KeyError as exc:
            raise RuntimeError(f"runtime node state missing: {node_id}") from exc

    @staticmethod
    def _checkpoint_fingerprint(
        run: AgentRun,
    ) -> tuple[RuntimeRunStatus, tuple[tuple[str, RuntimeNodeStatus], ...]]:
        """Return the state fields relevant to the preparation checkpoint."""

        return (
            run.status,
            tuple(
                (node_id, state.status)
                for node_id, state in run.nodes.items()
            ),
        )

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
