from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Collection

import pytest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeBudget,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeStateMachine,
)

RuntimeNodeHandler = Callable[
    [AgentRun, RuntimeNode], RuntimeObservation | Awaitable[RuntimeObservation]
]


class ProcessCrash(RuntimeError):
    """Test-only fault injection between handler completion and checkpoint."""


def _registry(
    handlers: dict[str, RuntimeNodeHandler],
    *,
    replay_safe: dict[str, bool] | None = None,
) -> RuntimeHandlerRegistry:
    registry = RuntimeHandlerRegistry()
    replay_safe = replay_safe or {}
    for handler_id, handler in handlers.items():
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id=handler_id,
                kind="tool",
                replay_safe=replay_safe.get(handler_id, True),
            ),
            handler,
        )
    return registry


def _run(
    nodes: list[RuntimeNode],
    *,
    run_id: str,
    max_parallelism: int = 2,
    budget: RuntimeBudget | None = None,
) -> AgentRun:
    plan = AgentRunPlan(
        plan_id=f"plan-{run_id}",
        goal="execute a bounded parallel runtime batch",
        max_parallelism=max_parallelism,
        nodes=nodes,
    )
    return AgentRun(
        run_id=run_id,
        task_id=f"task-{run_id}",
        goal=plan.goal,
        plan=plan,
        budget=budget or RuntimeBudget(max_tool_calls=16),
    )


@pytest.mark.asyncio
async def test_independent_parallel_group_nodes_execute_concurrently() -> None:
    active = 0
    max_active = 0
    entered = asyncio.Event()

    async def handler(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        if active == 2:
            entered.set()
        await asyncio.wait_for(entered.wait(), timeout=1)
        await asyncio.sleep(0)
        active -= 1
        return RuntimeObservation(node_id=node.node_id)

    run = _run(
        [
            RuntimeNode(
                node_id="source-a",
                node_type="tool",
                handler_id="source-a.handler",
                parallel_group="sources",
            ),
            RuntimeNode(
                node_id="source-b",
                node_type="tool",
                handler_id="source-b.handler",
                parallel_group="sources",
            ),
        ],
        run_id="parallel-batch",
    )

    await PlanExecutor(
        _registry(
            {"source-a.handler": handler, "source-b.handler": handler}
        )
    ).execute(run)

    assert max_active == 2
    assert run.status == RuntimeRunStatus.COMPLETED
    assert all(
        run.nodes[node_id].status == RuntimeNodeStatus.SUCCEEDED
        for node_id in ("source-a", "source-b")
    )


@pytest.mark.asyncio
async def test_safe_parallel_batch_recovery_replays_with_one_budget_charge() -> None:
    calls: list[str] = []
    checkpoints: list[dict[str, RuntimeNodeStatus]] = []
    crash_once = True

    def handler(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        calls.append(run.nodes[node.node_id].execution_key)
        return RuntimeObservation(node_id=node.node_id)

    async def checkpoint(run: AgentRun) -> None:
        checkpoints.append(
            {node_id: state.status for node_id, state in run.nodes.items()}
        )

    async def crash_after_batch(
        _run: AgentRun, _node_ids: Collection[str]
    ) -> None:
        nonlocal crash_once
        if crash_once:
            crash_once = False
            raise ProcessCrash("lost after external work, before completion checkpoint")

    run = _run(
        [
            RuntimeNode(
                node_id="safe-a",
                node_type="tool",
                handler_id="safe-a.handler",
                parallel_group="sources",
            ),
            RuntimeNode(
                node_id="safe-b",
                node_type="tool",
                handler_id="safe-b.handler",
                parallel_group="sources",
            ),
        ],
        run_id="parallel-safe-recovery",
        budget=RuntimeBudget(max_tool_calls=2),
    )
    registry = _registry(
        {"safe-a.handler": handler, "safe-b.handler": handler}
    )

    with pytest.raises(ProcessCrash):
        await PlanExecutor(
            registry,
            checkpoint_hook=checkpoint,
            after_batch_hook=crash_after_batch,
        ).execute(run)

    assert checkpoints[0] == {
        "safe-a": RuntimeNodeStatus.READY,
        "safe-b": RuntimeNodeStatus.READY,
    }
    assert checkpoints[-1] == {
        "safe-a": RuntimeNodeStatus.RUNNING,
        "safe-b": RuntimeNodeStatus.RUNNING,
    }
    assert run.budget.tool_calls == 2
    keys_before_recovery = {
        node_id: run.nodes[node_id].execution_key
        for node_id in ("safe-a", "safe-b")
    }

    restored = AgentRun.model_validate(run.model_dump(mode="json"))
    await PlanExecutor(registry, checkpoint_hook=checkpoint).execute(restored)

    assert restored.status == RuntimeRunStatus.COMPLETED
    assert restored.budget.tool_calls == 2
    assert len(calls) == 4
    assert sorted(calls[:2]) == sorted(keys_before_recovery.values())
    assert sorted(calls[2:]) == sorted(calls[:2])
    assert {
        node_id: restored.nodes[node_id].execution_key
        for node_id in keys_before_recovery
    } == keys_before_recovery


@pytest.mark.asyncio
async def test_mixed_recovery_reconciles_all_unsafe_nodes() -> None:
    calls: list[str] = []
    crash_once = True

    def handler(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        calls.append(node.node_id)
        return RuntimeObservation(node_id=node.node_id)

    async def crash_after_batch(
        _run: AgentRun, _node_ids: Collection[str]
    ) -> None:
        nonlocal crash_once
        if crash_once:
            crash_once = False
            raise ProcessCrash("lost after mixed batch")

    run = _run(
        [
            RuntimeNode(
                node_id="unsafe-first",
                node_type="tool",
                handler_id="unsafe.handler",
                parallel_group="mixed",
            ),
            RuntimeNode(
                node_id="safe-second",
                node_type="tool",
                handler_id="safe.handler",
                parallel_group="mixed",
            ),
        ],
        run_id="parallel-mixed-recovery",
        budget=RuntimeBudget(max_tool_calls=2),
    )
    registry = _registry(
        {"unsafe.handler": handler, "safe.handler": handler},
        replay_safe={"unsafe.handler": False, "safe.handler": True},
    )

    with pytest.raises(ProcessCrash):
        await PlanExecutor(
            registry, after_batch_hook=crash_after_batch
        ).execute(run)

    await PlanExecutor(registry).execute(run)

    assert len(calls) == 2
    assert set(calls) == {"unsafe-first", "safe-second"}
    assert run.status == RuntimeRunStatus.PAUSED
    assert run.nodes["safe-second"].status == RuntimeNodeStatus.READY
    assert run.nodes["safe-second"].error_code == ""
    assert run.nodes["safe-second"].budget_reservation == "replay_pending"
    assert run.nodes["unsafe-first"].status == RuntimeNodeStatus.RUNNING
    assert run.nodes["unsafe-first"].effect_status == RuntimeEffectStatus.UNKNOWN
    assert (
        run.nodes["unsafe-first"].error_code
        == "in_flight_execution_requires_reconciliation"
    )
    assert run.budget.tool_calls == 2

    restored = AgentRun.model_validate(run.model_dump(mode="json"))
    assert restored.nodes["safe-second"].error_code == ""
    assert restored.nodes["safe-second"].budget_reservation == "replay_pending"
    assert (
        restored.nodes["unsafe-first"].error_code
        == "in_flight_execution_requires_reconciliation"
    )

    # Reconciliation resolves the uncertain side effect without replaying the
    # unsafe handler. The next worker must still replay the safe node without
    # attempting a third tool-budget reservation.
    RuntimeStateMachine.complete_node(
        restored,
        "unsafe-first",
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(node_id="unsafe-first"),
    )
    await PlanExecutor(registry).execute(restored)

    assert restored.status == RuntimeRunStatus.COMPLETED
    assert restored.budget.tool_calls == 2
    assert restored.nodes["safe-second"].error_code == ""
    assert restored.nodes["safe-second"].budget_reservation == ""
    assert restored.nodes["unsafe-first"].error_code == ""
    assert calls.count("unsafe-first") == 1
    assert calls.count("safe-second") == 2


@pytest.mark.asyncio
async def test_replan_preserves_parallel_batch_dependencies() -> None:
    calls: list[str] = []

    def handler(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        calls.append(node.node_id)
        return RuntimeObservation(node_id=node.node_id)

    initial_nodes = [
        RuntimeNode(
            node_id="source-a",
            node_type="tool",
            handler_id="source-a.handler",
            parallel_group="sources",
        ),
        RuntimeNode(
            node_id="source-b",
            node_type="tool",
            handler_id="source-b.handler",
            parallel_group="sources",
        ),
        RuntimeNode(
            node_id="merge",
            node_type="tool",
            handler_id="merge.handler",
            depends_on=["source-a", "source-b"],
        ),
    ]
    run = _run(initial_nodes, run_id="parallel-replan")
    registry = _registry(
        {
            "source-a.handler": handler,
            "source-b.handler": handler,
            "merge.handler": handler,
            "publish.handler": handler,
        }
    )

    await PlanExecutor(registry).execute(run, node_ids=["source-a", "source-b"])
    assert set(calls) == {"source-a", "source-b"}
    assert len(calls) == 2
    assert run.nodes["merge"].status == RuntimeNodeStatus.READY

    RuntimeStateMachine.apply_decision(
        run,
        RuntimeDecision(
            action=DecisionAction.REPLAN,
            reason_codes=["add_publish_stage"],
        ),
    )
    replanned = AgentRunPlan(
        plan_id="parallel-replan-v2",
        version="2",
        goal=run.goal,
        max_parallelism=2,
        nodes=[
            initial_nodes[0],
            initial_nodes[1],
            initial_nodes[2],
            RuntimeNode(
                node_id="publish",
                node_type="tool",
                handler_id="publish.handler",
                depends_on=["merge"],
            ),
        ],
    )
    RuntimeStateMachine.replace_plan(run, replanned)

    assert run.nodes["source-a"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes["source-b"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes["merge"].status == RuntimeNodeStatus.PENDING
    assert run.plan.nodes[2].depends_on == ["source-a", "source-b"]
    assert run.plan.nodes[3].depends_on == ["merge"]

    await PlanExecutor(registry).execute(run)

    assert calls[-2:] == ["merge", "publish"]
    assert set(calls[:2]) == {"source-a", "source-b"}
    assert len(calls) == 4
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.iteration == 1
    assert run.budget.tool_calls == 4
