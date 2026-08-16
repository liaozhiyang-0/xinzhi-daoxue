from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime

from app.runtime.contracts import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeNodeActivation,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
)


class RuntimeStateMachine:
    """Pure state transitions for a future durable PlanExecutor.

    This class intentionally performs no I/O and invokes no Provider. Keeping
    transitions deterministic makes replay, checkpointing, and event testing
    possible without coupling state transitions to task transport.
    """

    TERMINAL_NODE_STATUSES = frozenset(
        {
            RuntimeNodeStatus.SUCCEEDED,
            RuntimeNodeStatus.PARTIAL,
            RuntimeNodeStatus.FAILED,
            RuntimeNodeStatus.SKIPPED,
            RuntimeNodeStatus.BLOCKED,
        }
    )

    @staticmethod
    def ready_nodes(run: AgentRun) -> list[str]:
        ready: list[str] = []
        states = run.nodes
        for node in run.plan.nodes:
            state = states[node.node_id]
            if state.status != RuntimeNodeStatus.PENDING:
                continue
            dependencies = [states[item].status for item in node.depends_on]
            if RuntimeStateMachine._activation_satisfied(
                node.activation,
                dependencies,
            ):
                ready.append(node.node_id)
        return ready

    @staticmethod
    def mark_ready(
        run: AgentRun, *, only_node_ids: Collection[str] | None = None
    ) -> AgentRun:
        allowed = set(only_node_ids) if only_node_ids is not None else None
        if allowed is not None:
            unknown = allowed - set(run.nodes)
            if unknown:
                raise ValueError(f"unknown runtime nodes: {sorted(unknown)}")
        for node_id in RuntimeStateMachine.ready_nodes(run):
            if allowed is not None and node_id not in allowed:
                continue
            run.nodes[node_id].status = RuntimeNodeStatus.READY
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def replace_plan(run: AgentRun, plan: AgentRunPlan) -> AgentRun:
        """Install a validated replan while preserving compatible successes."""

        if any(
            state.status == RuntimeNodeStatus.RUNNING
            for state in run.nodes.values()
        ):
            raise ValueError("cannot replace a plan while nodes are running")
        previous_nodes = {
            node.node_id: node for node in run.plan.nodes
        }
        previous_states = run.nodes
        next_states: dict[str, RuntimeNodeState] = {}
        for node in plan.nodes:
            previous = previous_nodes.get(node.node_id)
            previous_state = previous_states.get(node.node_id)
            compatible = (
                previous is not None
                and previous_state is not None
                and previous.handler_id == node.handler_id
                and previous.depends_on == node.depends_on
                and previous.activation == node.activation
                and previous.recovery_for == node.recovery_for
                and previous_state.status
                in {RuntimeNodeStatus.SUCCEEDED, RuntimeNodeStatus.SKIPPED}
            )
            if compatible and previous_state is not None:
                next_states[node.node_id] = previous_state
            else:
                next_states[node.node_id] = RuntimeNodeState(node_id=node.node_id)
        run.plan = plan
        if plan.goal_contract is not None:
            run.goal_contract = plan.goal_contract
        run.nodes = next_states
        run.status = RuntimeRunStatus.RUNNING
        run.completed_at = None
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def start_node(run: AgentRun, node_id: str) -> AgentRun:
        state = RuntimeStateMachine._node(run, node_id)
        if state.status != RuntimeNodeStatus.READY:
            raise ValueError(f"runtime node is not ready: {node_id}")
        if not run.budget.can_start_iteration():
            raise ValueError("runtime deadline exceeded")
        state.status = RuntimeNodeStatus.RUNNING
        state.attempt += 1
        if not state.execution_key:
            state.execution_key = f"{run.run_id}:{node_id}"
        if not state.reconciliation_id:
            state.reconciliation_id = f"runtime:{run.run_id}:{node_id}"
        state.effect_status = RuntimeEffectStatus.IN_PROGRESS
        state.started_at = datetime.now(UTC)
        if run.started_at is None:
            run.started_at = state.started_at
        run.status = RuntimeRunStatus.RUNNING
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def complete_node(
        run: AgentRun,
        node_id: str,
        *,
        status: RuntimeNodeStatus,
        observation: RuntimeObservation | None = None,
        error_code: str = "",
    ) -> AgentRun:
        if status not in RuntimeStateMachine.TERMINAL_NODE_STATUSES:
            raise ValueError(f"node completion requires terminal status: {status}")
        state = RuntimeStateMachine._node(run, node_id)
        if state.status != RuntimeNodeStatus.RUNNING:
            raise ValueError(f"runtime node is not running: {node_id}")
        if observation is not None and observation.node_id != node_id:
            raise ValueError("observation node_id does not match completed node")
        state.status = status
        state.effect_status = (
            RuntimeEffectStatus.COMPLETED
            if status
            in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.PARTIAL,
            }
            else RuntimeEffectStatus.UNKNOWN
        )
        state.observation = observation
        state.error_code = error_code
        state.completed_at = datetime.now(UTC)
        if observation is not None:
            run.observations.append(observation)
        run.updated_at = datetime.now(UTC)
        RuntimeStateMachine._refresh_run_status(run)
        return run

    @staticmethod
    def retry_node(run: AgentRun, node_id: str, *, error_code: str) -> AgentRun:
        state = RuntimeStateMachine._node(run, node_id)
        if state.status != RuntimeNodeStatus.RUNNING:
            raise ValueError(f"runtime node is not running: {node_id}")
        state.status = RuntimeNodeStatus.READY
        state.effect_status = RuntimeEffectStatus.UNKNOWN
        # A retry is a new execution attempt. Do not carry a durable marker
        # that only belongs to a recovered, already-charged safe replay.
        state.budget_reservation = ""
        state.error_code = error_code
        state.completed_at = None
        run.status = RuntimeRunStatus.RUNNING
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def block_node(run: AgentRun, node_id: str, *, error_code: str) -> AgentRun:
        state = RuntimeStateMachine._node(run, node_id)
        if state.status not in {
            RuntimeNodeStatus.PENDING,
            RuntimeNodeStatus.READY,
        }:
            raise ValueError(f"runtime node cannot be blocked: {node_id}")
        state.status = RuntimeNodeStatus.BLOCKED
        state.error_code = error_code
        state.completed_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)
        RuntimeStateMachine._refresh_run_status(run)
        return run

    @staticmethod
    def skip_node(run: AgentRun, node_id: str, *, reason: str) -> AgentRun:
        state = RuntimeStateMachine._node(run, node_id)
        if state.status not in {
            RuntimeNodeStatus.PENDING,
            RuntimeNodeStatus.READY,
        }:
            raise ValueError(f"runtime node cannot be skipped: {node_id}")
        state.status = RuntimeNodeStatus.SKIPPED
        state.error_code = reason
        state.completed_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)
        RuntimeStateMachine._refresh_run_status(run)
        return run

    @staticmethod
    def block_unreachable_nodes(run: AgentRun) -> AgentRun:
        """Mark nodes whose required dependencies can no longer succeed."""

        changed = True
        while changed:
            changed = False
            for node in run.plan.nodes:
                state = run.nodes[node.node_id]
                if state.status not in {
                    RuntimeNodeStatus.PENDING,
                    RuntimeNodeStatus.READY,
                }:
                    continue
                dependency_states = [run.nodes[item] for item in node.depends_on]
                dependency_statuses = [item.status for item in dependency_states]
                if node.activation == RuntimeNodeActivation.ALL_SUCCEEDED and any(
                    status in {RuntimeNodeStatus.FAILED, RuntimeNodeStatus.BLOCKED}
                    for status in dependency_statuses
                ):
                    RuntimeStateMachine.block_node(
                        run,
                        node.node_id,
                        error_code="dependency_failed",
                    )
                    changed = True
                elif (
                    node.activation == RuntimeNodeActivation.ANY_FAILED
                    and RuntimeStateMachine._dependencies_terminal(
                        dependency_statuses
                    )
                    and not RuntimeStateMachine._has_failed_dependency(
                        dependency_statuses
                    )
                ):
                    RuntimeStateMachine.skip_node(
                        run,
                        node.node_id,
                        reason="failure_condition_not_met",
                    )
                    changed = True
        return run

    @staticmethod
    def apply_decision(run: AgentRun, decision: RuntimeDecision) -> AgentRun:
        unknown = set(decision.node_ids) - set(run.nodes)
        if unknown:
            raise ValueError(f"decision references unknown nodes: {sorted(unknown)}")
        if decision.action == DecisionAction.EXECUTE:
            if not decision.node_ids:
                raise ValueError("execute decision requires node_ids")
            for node_id in decision.node_ids:
                if run.nodes[node_id].status == RuntimeNodeStatus.PENDING:
                    run.nodes[node_id].status = RuntimeNodeStatus.READY
            run.status = RuntimeRunStatus.RUNNING
        elif decision.action == DecisionAction.REPLAN:
            run.iteration += 1
            if run.iteration >= run.budget.max_iterations:
                run.status = RuntimeRunStatus.FAILED
                raise ValueError("runtime iteration budget exceeded")
            run.status = RuntimeRunStatus.RUNNING
        elif decision.action == DecisionAction.ASK_USER:
            if not decision.user_prompt:
                raise ValueError("ask_user decision requires user_prompt")
            run.status = RuntimeRunStatus.WAITING_INPUT
        elif decision.action == DecisionAction.REQUEST_APPROVAL:
            if not decision.approval_scope:
                raise ValueError("request_approval decision requires approval_scope")
            run.status = RuntimeRunStatus.WAITING_APPROVAL
        elif decision.action == DecisionAction.PAUSE:
            run.status = RuntimeRunStatus.PAUSED
        elif decision.action == DecisionAction.FINISH:
            run.status = RuntimeRunStatus.COMPLETED
            run.completed_at = datetime.now(UTC)
        elif decision.action == DecisionAction.FAIL:
            run.status = RuntimeRunStatus.FAILED
            run.completed_at = datetime.now(UTC)
        run.last_decision = decision
        run.decision_history.append(decision)
        if len(run.decision_history) > 500:
            del run.decision_history[:-500]
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def record_verification(
        run: AgentRun, observation: RuntimeObservation
    ) -> AgentRun:
        """Record a verifier result separately from node observations."""

        run.observations.append(observation)
        run.verification_history.append(observation)
        if len(run.observations) > 500:
            del run.observations[:-500]
        if len(run.verification_history) > 500:
            del run.verification_history[:-500]
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def _node(run: AgentRun, node_id: str) -> RuntimeNodeState:
        try:
            return run.nodes[node_id]
        except KeyError as exc:
            raise ValueError(f"unknown runtime node: {node_id}") from exc

    @staticmethod
    def _refresh_run_status(run: AgentRun) -> None:
        statuses = [state.status for state in run.nodes.values()]
        if any(status == RuntimeNodeStatus.RUNNING for status in statuses):
            run.status = RuntimeRunStatus.RUNNING
        elif all(
            status in RuntimeStateMachine.TERMINAL_NODE_STATUSES
            for status in statuses
        ):
            recovered = {
                recovered_node
                for node in run.plan.nodes
                if run.nodes[node.node_id].status == RuntimeNodeStatus.SUCCEEDED
                for recovered_node in node.recovery_for
            }
            unrecovered_failures = {
                node_id
                for node_id, state in run.nodes.items()
                if state.status in {
                    RuntimeNodeStatus.FAILED,
                    RuntimeNodeStatus.BLOCKED,
                }
                and node_id not in recovered
            }
            run.status = (
                RuntimeRunStatus.COMPLETED
                if not unrecovered_failures
                else RuntimeRunStatus.FAILED
            )
            if run.completed_at is None:
                run.completed_at = datetime.now(UTC)
        elif any(status == RuntimeNodeStatus.READY for status in statuses):
            run.status = RuntimeRunStatus.RUNNING

    @staticmethod
    def _dependencies_terminal(statuses: list[RuntimeNodeStatus]) -> bool:
        return all(
            status in RuntimeStateMachine.TERMINAL_NODE_STATUSES
            for status in statuses
        )

    @staticmethod
    def _has_failed_dependency(statuses: list[RuntimeNodeStatus]) -> bool:
        return any(
            status in {RuntimeNodeStatus.FAILED, RuntimeNodeStatus.BLOCKED}
            for status in statuses
        )

    @staticmethod
    def _activation_satisfied(
        activation: RuntimeNodeActivation,
        statuses: list[RuntimeNodeStatus],
    ) -> bool:
        if activation == RuntimeNodeActivation.ALL_SUCCEEDED:
            return all(
                status
                in {RuntimeNodeStatus.SUCCEEDED, RuntimeNodeStatus.SKIPPED}
                for status in statuses
            )
        if not RuntimeStateMachine._dependencies_terminal(statuses):
            return False
        if activation == RuntimeNodeActivation.ANY_FAILED:
            return RuntimeStateMachine._has_failed_dependency(statuses)
        return True
