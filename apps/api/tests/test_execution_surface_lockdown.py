from __future__ import annotations

from dataclasses import dataclass

import pytest
from app.runtime import RuntimeHandlerDescriptor, RuntimeHandlerRegistry
from app.runtime.contracts import AgentRunPlan, RuntimeNode
from app.runtime.handler_registry import RuntimeHandlerRegistryError
from app.services.production_execution_manifest import (
    ExecutionSurfaceError,
    LegacyExecutionForbidden,
    ProductionExecutionManifest,
)
from app.tools import ToolDefinition, ToolRegistry


@dataclass(frozen=True)
class Binding:
    capability_id: str
    handler_id: str


class CurrentRuntime:
    execute_handler_id = "current.execute"
    tool_handler_prefix = "current.tool"


def _manifest() -> ProductionExecutionManifest:
    handlers = RuntimeHandlerRegistry()
    handlers.register(
        RuntimeHandlerDescriptor(handler_id="provider.default", kind="provider"),
        lambda _run, _node: None,
    )
    handlers.register(
        RuntimeHandlerDescriptor(handler_id="subagent.CURRENT", kind="subagent"),
        lambda _run, _node: None,
    )
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            tool_id="calculator",
            name="calculator",
            supported_capabilities=frozenset(),
            input_schema={},
            output_schema={},
        ),
        lambda **_kwargs: {},
    )
    return ProductionExecutionManifest.build(
        planner_version="planner-v1",
        capability_bindings=[Binding("current.answer", "CURRENT")],
        tool_registry=tools,
        runtime_handler_registry=handlers,
        business_services=[CurrentRuntime()],
        provider_mode="local",
        build_id="test-build",
    )


def test_manifest_rejects_quarantined_and_unknown_targets() -> None:
    manifest = _manifest()

    with pytest.raises(LegacyExecutionForbidden):
        manifest.validate_handler("provider.default", caller="test")
    with pytest.raises(ExecutionSurfaceError, match="not active"):
        manifest.validate_handler("old-router.execute", caller="test")


def test_manifest_fences_task_metadata_and_runtime_plan() -> None:
    manifest = _manifest()
    assert manifest.active_tool_hash
    assert manifest.identity_payload()["active_tool_hash"] == manifest.active_tool_hash
    metadata = manifest.task_metadata()
    manifest.validate_task_envelope({"options": {"_execution_surface": metadata}})

    stale = dict(metadata)
    stale["runtime_generation"] = "runtime-v2"
    with pytest.raises(ExecutionSurfaceError, match="does not match"):
        manifest.validate_task_envelope(
            {"options": {"_execution_surface": stale}}
        )

    plan = AgentRunPlan(
        plan_id="current-plan",
        version="canonical-v1",
        goal="answer",
        nodes=[
            RuntimeNode(
                node_id="answer",
                node_type="subagent",
                handler_id="subagent.CURRENT",
            )
        ],
    )
    manifest.validate_runtime_plan(plan)

    forbidden_plan = plan.model_copy(
        update={
            "plan_id": "legacy-runtime:CURRENT",
        }
    )
    with pytest.raises(LegacyExecutionForbidden):
        manifest.validate_runtime_plan(forbidden_plan)


def test_executable_registry_freezes_after_bootstrap() -> None:
    registry = RuntimeHandlerRegistry()
    registry.register(
        RuntimeHandlerDescriptor(handler_id="current.execute", kind="agent"),
        lambda _run, _node: None,
    )
    registry.freeze()

    with pytest.raises(RuntimeHandlerRegistryError, match="frozen"):
        registry.register(
            RuntimeHandlerDescriptor(handler_id="late.execute", kind="agent"),
            lambda _run, _node: None,
        )
