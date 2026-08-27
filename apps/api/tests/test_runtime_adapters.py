from __future__ import annotations

import asyncio
from typing import Any

from app.contracts import AgentRequest, AgentResult
from app.providers.base import AgentProvider
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    PlanExecutor,
    RuntimeNode,
    RuntimeNodeStatus,
    build_runtime_handler_registry,
)
from app.tools import default_tool_registry
from app.tools.registry import ToolDefinition, ToolRegistry


def make_run(
    node: RuntimeNode,
    *,
    control_data: dict[str, Any] | None = None,
) -> AgentRun:
    return AgentRun(
        run_id=f"run-{node.node_id}",
        task_id=f"task-{node.node_id}",
        goal="adapter test",
        plan=AgentRunPlan(
            plan_id=f"plan-{node.node_id}",
            goal="adapter test",
            nodes=[node],
        ),
        control_data=control_data or {},
    )


class FakeProvider(AgentProvider):
    provider_name = "fake"

    def __init__(self) -> None:
        self.last_request: AgentRequest | None = None

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        self.last_request = request
        return AgentResult(
            agent_id=agent_id,
            provider=self.provider_name,
            answer=request.canonical_input.get("text", ""),
            structured_result={"stream": stream},
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed"}


class FakeInternalAgents:
    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: Any = None,
    ) -> AgentResult:
        assert context is None
        return AgentResult(
            agent_id=agent_id,
            provider="internal",
            answer=request.canonical_input.get("text", ""),
            structured_result={"internal": True},
        )


def test_runtime_adapters_register_and_execute_existing_capabilities() -> None:
    provider = FakeProvider()
    registry = build_runtime_handler_registry(
        default_tool_registry(),
        provider,
        FakeInternalAgents(),
    )

    tool_run = make_run(
        RuntimeNode(
            node_id="calculator",
            node_type="tool",
            handler_id="tool.calculator",
            timeout_ms=10_000,
        ),
        control_data={
            "node_inputs": {"calculator": {"expression": "2 + 3"}}
        },
    )
    asyncio.run(PlanExecutor(registry).execute(tool_run))
    assert tool_run.status.value == "completed"
    assert tool_run.nodes["calculator"].status == RuntimeNodeStatus.SUCCEEDED
    assert tool_run.nodes["calculator"].observation is not None
    assert tool_run.nodes["calculator"].observation.facts["output"] == 5

    request = AgentRequest(
        session_id="session-adapter",
        user_id="user-adapter",
        canonical_input={"text": "provider input"},
    )
    provider_run = make_run(
        RuntimeNode(
            node_id="provider",
            node_type="provider",
            handler_id="provider.default",
            target_id="PROVIDER_AGENT",
        ),
        control_data={"request": request.model_dump(mode="json")},
    )
    asyncio.run(PlanExecutor(registry).execute(provider_run))
    assert provider_run.status.value == "completed"
    assert provider_run.nodes["provider"].observation is not None
    assert provider_run.nodes["provider"].observation.facts["agent_id"] == (
        "PROVIDER_AGENT"
    )
    assert provider_run.nodes["provider"].observation.facts["structured_result"] == {
        "stream": False
    }

    internal_run = make_run(
        RuntimeNode(
            node_id="internal",
            node_type="subagent",
            handler_id="agent.internal",
            target_id="INTERNAL_AGENT",
        ),
        control_data={"request": request.model_dump(mode="json")},
    )
    asyncio.run(PlanExecutor(registry).execute(internal_run))
    assert internal_run.status.value == "completed"
    assert internal_run.nodes["internal"].observation is not None
    assert internal_run.nodes["internal"].observation.facts["provider"] == (
        "internal"
    )


def test_default_tools_publish_required_input_contracts() -> None:
    tools = default_tool_registry()

    assert tools.describe("calculator").input_schema["required"] == [
        "expression"
    ]
    assert tools.describe("sympy_solver").input_schema["required"] == [
        "equations",
        "symbols",
    ]
    assert tools.describe("unit_checker").input_schema["required"] == [
        "left",
        "right",
    ]


def test_runtime_tool_schema_validates_call_kwargs_and_normalizes_errors() -> None:
    registry = build_runtime_handler_registry(default_tool_registry(), FakeProvider())
    invalid_run = make_run(
        RuntimeNode(
            node_id="calculator",
            node_type="tool",
            handler_id="tool.calculator",
            timeout_ms=10_000,
        ),
        control_data={"node_inputs": {"calculator": {}}},
    )

    asyncio.run(PlanExecutor(registry).execute(invalid_run))

    assert invalid_run.status.value == "failed"
    assert invalid_run.nodes["calculator"].error_code == (
        "node_input_schema_required"
    )

    failed_run = make_run(
        RuntimeNode(
            node_id="calculator",
            node_type="tool",
            handler_id="tool.calculator",
            timeout_ms=10_000,
        ),
        control_data={
            "node_inputs": {"calculator": {"expression": "not valid"}}
        },
    )
    asyncio.run(PlanExecutor(registry).execute(failed_run))

    assert failed_run.status.value == "failed"
    assert failed_run.nodes["calculator"].error_code == "tool_execution_failed"


def test_runtime_tool_descriptors_preserve_schema_and_execution_policy() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            tool_id="calculator",
            name="Calculator",
            supported_capabilities=frozenset({"algebra"}),
            input_schema={
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
            output_schema={"type": "number"},
        ),
        lambda expression: len(expression),
    )
    tools.register(
        ToolDefinition(
            tool_id="sandbox_writer",
            name="Sandbox writer",
            supported_capabilities=frozenset({"code_analysis"}),
            input_schema={"type": "object", "required": ["code"]},
            output_schema={"type": "object"},
            side_effect_level="write",
            requires_sandbox=True,
            deterministic=False,
        ),
        lambda code: {"length": len(code)},
    )

    runtime_registry = build_runtime_handler_registry(
        tools,
        FakeProvider(),
    )

    calculator = runtime_registry.descriptor("tool.calculator")
    assert calculator.input_schema == {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    }
    assert calculator.output_schema == {"type": "number"}
    assert calculator.permission_scope == "tool.calculator"
    assert calculator.side_effect_level == "none"
    assert calculator.requires_sandbox is False
    assert calculator.risk_level == "low"
    assert calculator.requires_approval is False
    assert calculator.replay_safe is True

    sandbox_writer = runtime_registry.descriptor("tool.sandbox_writer")
    assert sandbox_writer.input_schema == {
        "type": "object",
        "required": ["code"],
    }
    assert sandbox_writer.output_schema == {"type": "object"}
    assert sandbox_writer.permission_scope == "tool.sandbox_writer"
    assert sandbox_writer.side_effect_level == "write"
    assert sandbox_writer.requires_sandbox is True
    assert sandbox_writer.risk_level == "high"
    assert sandbox_writer.requires_approval is True
    assert sandbox_writer.side_effecting is True
    assert sandbox_writer.replay_safe is False


def test_runtime_handler_descriptor_defaults_remain_backward_compatible() -> None:
    from app.runtime.handler_registry import RuntimeHandlerDescriptor

    descriptor = RuntimeHandlerDescriptor(handler_id="legacy", kind="tool")

    assert descriptor.input_schema == {}
    assert descriptor.output_schema == {}
    assert descriptor.permission_scope == "runtime"
    assert descriptor.side_effect_level == "none"
    assert descriptor.requires_sandbox is False
    assert descriptor.risk_level == "low"


def test_runtime_tool_input_schema_rejects_missing_required_before_call() -> None:
    calls: list[dict[str, Any]] = []
    tools = ToolRegistry()

    def handler(**payload: Any) -> dict[str, Any]:
        calls.append(payload)
        return payload

    tools.register(
        ToolDefinition(
            tool_id="strict_tool",
            name="Strict tool",
            supported_capabilities=frozenset(),
            input_schema={
                "type": "object",
                "required": ["expression"],
                "properties": {"expression": {"type": "string"}},
            },
            output_schema={"type": "object"},
        ),
        handler,
    )
    registry = build_runtime_handler_registry(tools, FakeProvider())
    run = make_run(
        RuntimeNode(
            node_id="strict",
            node_type="tool",
            handler_id="tool.strict_tool",
            timeout_ms=10_000,
        ),
        control_data={"node_inputs": {"strict": {}}},
    )

    asyncio.run(PlanExecutor(registry).execute(run))

    assert run.status.value == "failed"
    assert run.nodes["strict"].error_code == "node_input_schema_required"
    assert calls == []


def test_runtime_tool_input_schema_rejects_wrong_property_type() -> None:
    calls: list[dict[str, Any]] = []
    tools = ToolRegistry()

    def handler(**payload: Any) -> dict[str, Any]:
        calls.append(payload)
        return payload

    tools.register(
        ToolDefinition(
            tool_id="typed_tool",
            name="Typed tool",
            supported_capabilities=frozenset(),
            input_schema={
                "type": "object",
                "properties": {"expression": {"type": "string"}},
            },
            output_schema={"type": "object"},
        ),
        handler,
    )
    registry = build_runtime_handler_registry(tools, FakeProvider())
    run = make_run(
        RuntimeNode(
            node_id="typed",
            node_type="tool",
            handler_id="tool.typed_tool",
            timeout_ms=10_000,
        ),
        control_data={"node_inputs": {"typed": {"expression": 42}}},
    )

    asyncio.run(PlanExecutor(registry).execute(run))

    assert run.status.value == "failed"
    assert run.nodes["typed"].error_code == "node_input_schema_type_mismatch"
    assert calls == []


def test_runtime_request_adapter_propagates_resumed_user_input() -> None:
    provider = FakeProvider()
    registry = build_runtime_handler_registry(
        default_tool_registry(),
        provider,
        FakeInternalAgents(),
    )
    request = AgentRequest(
        task_id="task-input-adapter",
        session_id="session-adapter",
        user_id="user-adapter",
        canonical_input={"text": "resume"},
    )
    run = make_run(
        RuntimeNode(
            node_id="provider",
            node_type="provider",
            handler_id="provider.default",
            target_id="PROVIDER_AGENT",
        ),
        control_data={
            "request": request.model_dump(mode="json"),
            "user_input": {"confirmed": True},
        },
    )

    asyncio.run(PlanExecutor(registry).execute(run))

    assert run.nodes["provider"].observation is not None
    assert run.nodes["provider"].observation.facts["structured_result"] == {
        "stream": False
    }
    assert provider.last_request is not None
    assert provider.last_request.options["runtime_user_input"] == {"confirmed": True}


def test_runtime_request_adapter_injects_dependency_observations() -> None:
    provider = FakeProvider()
    registry = build_runtime_handler_registry(
        default_tool_registry(),
        provider,
        FakeInternalAgents(),
    )
    request = AgentRequest(
        task_id="task-dependency-adapter",
        session_id="session-adapter",
        user_id="user-adapter",
        canonical_input={"text": "continue"},
    )
    run = AgentRun(
        run_id="run-dependency-adapter",
        task_id="task-dependency-adapter",
        goal="dependency context",
        plan=AgentRunPlan(
            plan_id="plan-dependency-adapter",
            goal="dependency context",
            nodes=[
                RuntimeNode(
                    node_id="observe",
                    node_type="tool",
                    handler_id="tool.calculator",
                    timeout_ms=10_000,
                ),
                RuntimeNode(
                    node_id="decide",
                    node_type="provider",
                    handler_id="provider.default",
                    target_id="PROVIDER_AGENT",
                    depends_on=["observe"],
                ),
            ],
        ),
        control_data={
            "request": request.model_dump(mode="json"),
            "node_inputs": {"observe": {"expression": "2 + 3"}},
        },
    )

    asyncio.run(PlanExecutor(registry).execute(run))

    assert provider.last_request is not None
    dependency = provider.last_request.options["runtime_context"]["dependencies"][
        "observe"
    ]
    assert dependency["status"] == "succeeded"
    assert dependency["facts"]["output"] == 5
