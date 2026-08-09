from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.contracts import AgentRequest, AgentResult
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    PlanExecutor,
    RuntimeBudget,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeSubagentDefinition,
    RuntimeSubagentRegistry,
    register_subagent_handlers,
)


class FakeInternalAgents:
    def __init__(self) -> None:
        self.calls: list[tuple[str, AgentRequest, Any]] = []

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: Any = None,
    ) -> AgentResult:
        self.calls.append((agent_id, request, context))
        return AgentResult(
            agent_id=agent_id,
            provider="internal",
            answer="sub-agent answer",
            structured_result={"ok": True},
            artifacts=[],
        )


def make_subagent_run(
    *,
    target_id: str = "LOCAL_SOLVER",
    budget: RuntimeBudget | None = None,
) -> AgentRun:
    request = AgentRequest(
        task_id="task-subagent",
        session_id="session-subagent",
        user_id="user-subagent",
        canonical_input={"text": "solve this"},
    )
    return AgentRun(
        run_id="run-subagent",
        task_id="task-subagent",
        goal="test sub-agent execution",
        plan=AgentRunPlan(
            plan_id="plan-subagent",
            goal="test sub-agent execution",
            nodes=[
                RuntimeNode(
                    node_id="delegate",
                    node_type="subagent",
                    handler_id="subagent.solver",
                    target_id=target_id,
                    timeout_ms=5_000,
                )
            ],
        ),
        budget=budget or RuntimeBudget(),
        control_data={"request": request.model_dump(mode="json")},
    )


def make_registry(
    internal_agents: FakeInternalAgents,
    *,
    requires_approval: bool = False,
) -> RuntimeHandlerRegistry:
    subagents = RuntimeSubagentRegistry()
    subagents.register(
        RuntimeSubagentDefinition(
            subagent_id="solver",
            target_agent_id="LOCAL_SOLVER",
            version="2",
            requires_approval=requires_approval,
            max_timeout_ms=10_000,
        )
    )
    registry = RuntimeHandlerRegistry()
    register_subagent_handlers(registry, internal_agents, subagents)
    return registry


def test_typed_subagent_registration_and_execution_is_bounded() -> None:
    internal_agents = FakeInternalAgents()
    registry = make_registry(internal_agents)
    run = make_subagent_run()

    asyncio.run(PlanExecutor(registry).execute(run))

    assert run.status.value == "completed"
    assert run.nodes["delegate"].status == RuntimeNodeStatus.SUCCEEDED
    assert len(internal_agents.calls) == 1
    agent_id, request, context = internal_agents.calls[0]
    assert agent_id == "LOCAL_SOLVER"
    assert context is None
    assert request.options["runtime_execution_key"] == (
        "run-subagent:subagent:delegate"
    )
    assert request.options["runtime_parent_run_id"] == "run-subagent"
    assert request.options["runtime_subagent_id"] == "solver"
    observation = run.nodes["delegate"].observation
    assert observation is not None
    assert observation.facts["subagent_run_id"] == "run-subagent:subagent:delegate"
    assert observation.facts["target_agent_id"] == "LOCAL_SOLVER"
    assert observation.facts["answer"] == "sub-agent answer"

    descriptor = registry.descriptor("subagent.solver")
    assert descriptor.version == "2"
    assert descriptor.max_timeout_ms == 10_000
    assert descriptor.kind == "subagent"


def test_subagent_registry_rejects_duplicates_and_skips_disabled_handlers() -> None:
    subagents = RuntimeSubagentRegistry()
    definition = RuntimeSubagentDefinition(
        subagent_id="solver",
        target_agent_id="LOCAL_SOLVER",
    )
    subagents.register(definition)
    with pytest.raises(ValueError):
        subagents.register(definition)

    subagents.register(
        RuntimeSubagentDefinition(
            subagent_id="disabled",
            target_agent_id="LOCAL_DISABLED",
            enabled=False,
        )
    )
    registry = RuntimeHandlerRegistry()
    registered = register_subagent_handlers(
        registry, FakeInternalAgents(), subagents
    )
    assert registered == ["subagent.solver"]
    with pytest.raises(RuntimeError):
        registry.descriptor("subagent.disabled")


def test_subagent_budget_is_reserved_before_handler_invocation() -> None:
    internal_agents = FakeInternalAgents()
    run = make_subagent_run(budget=RuntimeBudget(max_subagent_runs=0))

    asyncio.run(PlanExecutor(make_registry(internal_agents)).execute(run))

    assert internal_agents.calls == []
    assert run.nodes["delegate"].status == RuntimeNodeStatus.FAILED
    assert run.nodes["delegate"].error_code == "subagent_budget_exceeded"


def test_subagent_target_cannot_escape_registered_policy() -> None:
    internal_agents = FakeInternalAgents()
    run = make_subagent_run(target_id="UNREGISTERED_AGENT")

    asyncio.run(PlanExecutor(make_registry(internal_agents)).execute(run))

    assert internal_agents.calls == []
    assert run.nodes["delegate"].status == RuntimeNodeStatus.FAILED
    assert run.nodes["delegate"].error_code == "subagent_target_policy_mismatch"


def test_subagent_approval_policy_is_exposed_to_executor() -> None:
    internal_agents = FakeInternalAgents()
    run = make_subagent_run()
    registry = make_registry(internal_agents, requires_approval=True)

    asyncio.run(PlanExecutor(registry).execute(run))

    assert internal_agents.calls == []
    assert run.status.value == "waiting_approval"
    assert run.last_decision is not None
    assert run.last_decision.approval_scope == "subagent.solver"
