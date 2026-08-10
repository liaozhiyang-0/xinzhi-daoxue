from __future__ import annotations

import pytest
from app.contracts import AgentRequest, AgentResultStatus
from app.runtime import (
    AgentRun,
    RuntimeGoal,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.generic_goal_runtime import GenericGoalRuntimeService
from app.services.runtime_business_registry import RuntimeBusinessRegistry
from app.services.runtime_goal_intake import RuntimeGoalIntakePolicy


def _request(
    *,
    capability: str,
    execute: bool = True,
    fallback_capabilities: list[str] | None = None,
) -> AgentRequest:
    constraints = (
        {"fallback_capabilities": fallback_capabilities}
        if fallback_capabilities is not None
        else {}
    )
    return AgentRequest(
        task_id="task-generic-goal",
        session_id="session-generic-goal",
        user_id="user-generic-goal",
        options={
            "runtime_goal_runtime": {
                "execute": execute,
                "goal": RuntimeGoal(
                    objective="complete a declared capability",
                    success_criteria=["the capability succeeds"],
                    constraints=constraints,
                    required_capabilities=[capability],
                ).model_dump(mode="json"),
            }
        },
    )


def _registry(*, requires_approval: bool = False) -> RuntimeHandlerRegistry:
    registry = RuntimeHandlerRegistry()

    async def execute(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        assert isinstance(run.control_data.get("request"), dict)
        return RuntimeObservation(
            node_id=node.node_id,
            facts={"output": "declared capability completed"},
        )

    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="tool.declared",
            kind="tool",
            requires_approval=requires_approval,
            side_effecting=requires_approval,
            replay_safe=not requires_approval,
        ),
        execute,
    )
    return registry


def _replanning_registry() -> RuntimeHandlerRegistry:
    registry = RuntimeHandlerRegistry()

    def primary(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        del run
        return RuntimeObservation(
            node_id=node.node_id,
            terminal_status=RuntimeNodeStatus.FAILED,
            facts={"error": "primary unavailable"},
        )

    def fallback(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        assert isinstance(run.control_data.get("request"), dict)
        return RuntimeObservation(
            node_id=node.node_id,
            facts={"output": "fallback completed"},
        )

    registry.register(
        RuntimeHandlerDescriptor(handler_id="tool.primary", kind="tool"),
        primary,
    )
    registry.register(
        RuntimeHandlerDescriptor(handler_id="tool.fallback", kind="tool"),
        fallback,
    )
    return registry


@pytest.mark.asyncio
async def test_explicit_goal_runtime_executes_registered_capability() -> None:
    service = GenericGoalRuntimeService(_registry())
    request = _request(capability="tool.declared")
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="runtime-generic-goal",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
        request_snapshot=request.model_dump(mode="json"),
    )
    checkpoints: list[RuntimeRunStatus] = []
    events: list[str] = []

    result = await service.run(
        request,
        run,
        checkpoint_hook=lambda current: checkpoints.append(current.status),
        event_hook=lambda event, _current, _node: events.append(event),
    )

    assert result.status == AgentResultStatus.COMPLETED
    assert result.answer == "declared capability completed"
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.nodes["goal.step.1.tool-declared"].status.value == "succeeded"
    assert checkpoints
    assert "node_started" in events
    assert "node_completed" in events


@pytest.mark.asyncio
async def test_goal_runtime_pauses_for_approval_and_resumes() -> None:
    service = GenericGoalRuntimeService(
        _registry(requires_approval=True),
        intake_policy=RuntimeGoalIntakePolicy.from_config(
            "request=tool.declared"
        ),
    )
    request = _request(capability="tool.declared")
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="runtime-generic-approval",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
        request_snapshot=request.model_dump(mode="json"),
    )

    with pytest.raises(RuntimeRunSuspended):
        await service.run(request, run)
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL

    run.control_data.update(
        {"approved": True, "approved_scope": "tool.declared"}
    )
    result = await service.run(request, run)

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED


@pytest.mark.asyncio
async def test_goal_runtime_replans_to_policy_checked_fallback() -> None:
    registry = _replanning_registry()
    service = GenericGoalRuntimeService(registry)
    request = _request(
        capability="tool.primary",
        fallback_capabilities=["tool.fallback"],
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="runtime-generic-replan",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
        request_snapshot=request.model_dump(mode="json"),
    )

    result = await service.run(request, run)

    assert result.answer == "fallback completed"
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.iteration == 1
    assert run.plan.nodes[0].handler_id == "tool.fallback"
    assert any(
        item.facts.get("error") == "primary unavailable"
        for item in run.observations
    )


def test_goal_runtime_requires_explicit_opt_in() -> None:
    service = GenericGoalRuntimeService(_registry())

    assert service.supports("ANY_AGENT", _request(capability="tool.declared"))
    assert not service.supports(
        "ANY_AGENT", _request(capability="tool.declared", execute=False)
    )


def test_registry_passes_actual_agent_to_goal_intake() -> None:
    service = GenericGoalRuntimeService(_registry())
    registry = RuntimeBusinessRegistry([service])

    plan = registry.build_plan(
        "ACTUAL_AGENT", _request(capability="tool.declared")
    )

    assert plan is not None
    assert plan.goal_contract is not None
    intake = plan.goal_contract.context["intake"]
    assert intake["agent_id"] == "ACTUAL_AGENT"


def test_goal_runtime_renders_scalar_tool_output_as_answer() -> None:
    run = AgentRun(
        run_id="runtime-generic-scalar-output",
        task_id="task-generic-scalar-output",
        goal="render scalar output",
        plan=GenericGoalRuntimeService(_registry()).build_plan(
            _request(capability="tool.declared")
        ),
    )
    node_id = next(iter(run.nodes))
    run.nodes[node_id].observation = RuntimeObservation(
        node_id=node_id,
        facts={"output": 5},
    )

    assert GenericGoalRuntimeService._answer(run) == "5"
