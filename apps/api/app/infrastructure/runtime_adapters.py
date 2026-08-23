"""Adapters from existing capability registries to Runtime handlers.

The adapters keep the Runtime contract independent from concrete tools and
providers. Node inputs are supplied through the bounded ``control_data``
envelope under ``node_inputs[node_id]``; plans decide the target explicitly via
``RuntimeNode.target_id``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from app.contracts import AgentRequest, AgentResultStatus
from app.providers.base import AgentProvider
from app.runtime.contracts import (
    AgentRun,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
)
from app.runtime.executor import RuntimeNodeError
from app.runtime.handler_registry import (
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeHandlerRegistryError,
    RuntimeRiskLevel,
)
from app.runtime.subagents import (
    RuntimeSubagentDefinition,
    RuntimeSubagentRegistry,
)
from app.tools.registry import ToolRegistry


def _node_input(run: AgentRun, node: RuntimeNode) -> dict[str, Any]:
    raw_inputs = run.control_data.get("node_inputs", {})
    if not isinstance(raw_inputs, Mapping):
        raise RuntimeNodeError("node_inputs_invalid")
    payload = raw_inputs.get(node.node_id, {})
    if not isinstance(payload, Mapping):
        raise RuntimeNodeError("node_input_invalid")
    return dict(payload)


def _request_input(run: AgentRun, node: RuntimeNode) -> AgentRequest:
    payload = run.control_data.get("request")
    if not isinstance(payload, Mapping):
        raise RuntimeNodeError("agent_request_missing")
    try:
        request = AgentRequest.model_validate(payload)
    except ValueError as exc:
        raise RuntimeNodeError("agent_request_invalid") from exc
    options = dict(request.options)
    options["runtime_execution_key"] = run.nodes[node.node_id].execution_key
    options["runtime_context"] = _dependency_context(run, node)
    user_input = run.control_data.get("user_input")
    if isinstance(user_input, Mapping):
        options["runtime_user_input"] = dict(user_input)
    return request.model_copy(update={"options": options})


def _dependency_context(run: AgentRun, node: RuntimeNode) -> dict[str, Any]:
    """Expose bounded, explicit upstream observations to a downstream handler."""

    dependencies: dict[str, Any] = {}
    for dependency_id in node.depends_on[:32]:
        state = run.nodes.get(dependency_id)
        if state is None:
            continue
        observation = state.observation
        dependencies[dependency_id] = {
            "status": state.status.value,
            "error_code": state.error_code,
            "facts": _safe_value(observation.facts) if observation else {},
            "artifact_ids": list(observation.artifact_ids[:100])
            if observation
            else [],
            "evidence_ids": list(observation.evidence_ids[:100])
            if observation
            else [],
            "warnings": list(observation.warnings[:16]) if observation else [],
        }
    return {"dependencies": dependencies}


def _safe_value(value: Any, *, max_chars: int = 20_000) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_value(item, max_chars=max_chars)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, max_chars=max_chars) for item in value[:100]]
    return repr(value)[:max_chars]


def _tool_risk_level(definition: Any) -> RuntimeRiskLevel:
    """Project tool side-effect and sandbox metadata into Runtime risk tiers.

    ToolDefinition intentionally keeps ``side_effect_level`` extensible. An
    unknown non-read-only value therefore fails closed to ``high`` instead of
    being treated as a harmless tool. Sandboxing a read-only tool still has an
    execution-isolation risk and is represented as ``medium``.
    """

    side_effect_level = str(definition.side_effect_level).strip().lower()
    if side_effect_level in {"delete", "destructive", "critical"}:
        return "critical"
    if side_effect_level not in {"none", "read_only"}:
        return "high"
    if definition.requires_sandbox:
        return "medium"
    return "low"


async def _invoke(handler: Callable[..., Any], payload: Mapping[str, Any]) -> Any:
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", payload)
    if not isinstance(args, list) or not isinstance(kwargs, Mapping):
        raise RuntimeNodeError("node_input_call_shape_invalid")
    # ``args``/``kwargs`` are the only generic calling convention. A plain
    # payload is treated as kwargs for ergonomic use by declarative plans.
    result = handler(*args, **dict(kwargs))
    if inspect.isawaitable(result):
        return await result
    return result


def register_tool_handlers(
    runtime_registry: RuntimeHandlerRegistry,
    tool_registry: ToolRegistry,
) -> list[str]:
    """Register enabled existing tools without changing their implementations."""

    registered: list[str] = []
    for definition in tool_registry.list_tools():
        if not definition.enabled:
            continue
        handler = tool_registry.get(definition.tool_id)
        handler_id = f"tool.{definition.tool_id}"
        requires_approval = (
            definition.side_effect_level not in {"none", "read_only"}
            or definition.requires_sandbox
        )

        async def execute(
            run: AgentRun,
            node: RuntimeNode,
            *,
            _handler: Callable[..., Any] = handler,
            _tool_id: str = definition.tool_id,
            _handler_id: str = handler_id,
        ) -> RuntimeObservation:
            payload = _node_input(run, node)
            try:
                runtime_registry.validate_input(_handler_id, payload)
            except RuntimeHandlerRegistryError as exc:
                raise RuntimeNodeError(exc.error_code, str(exc)) from exc
            result = await _invoke(_handler, payload)
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "tool_id": _tool_id,
                    "execution_key": run.nodes[node.node_id].execution_key,
                    "output": _safe_value(result),
                },
            )

        runtime_registry.register(
            RuntimeHandlerDescriptor(
                handler_id=handler_id,
                kind="tool",
                version="1",
                input_schema=definition.input_schema,
                output_schema=definition.output_schema,
                permission_scope=handler_id,
                side_effect_level=definition.side_effect_level,
                requires_sandbox=definition.requires_sandbox,
                risk_level=_tool_risk_level(definition),
                requires_approval=requires_approval,
                side_effecting=requires_approval,
                replay_safe=not requires_approval,
                max_timeout_ms=max(
                    100, min(900_000, int(definition.timeout_seconds * 1000))
                ),
            ),
            execute,
        )
        registered.append(handler_id)
    return registered


def register_provider_handler(
    runtime_registry: RuntimeHandlerRegistry,
    provider: AgentProvider,
    *,
    handler_id: str = "provider.default",
    requires_approval: bool = False,
) -> None:
    async def execute(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        if not node.target_id:
            raise RuntimeNodeError("provider_target_missing")
        request = _request_input(run, node)
        result = await provider.run(node.target_id, request, stream=False)
        status = (
            RuntimeNodeStatus.PARTIAL
            if result.status == AgentResultStatus.FAILED
            else RuntimeNodeStatus.SUCCEEDED
        )
        return RuntimeObservation(
            node_id=node.node_id,
            terminal_status=status,
            artifact_ids=[item.artifact_id for item in result.artifacts],
            facts={
                "agent_id": result.agent_id,
                "provider": result.provider,
                "result_status": result.status.value,
                "execution_key": run.nodes[node.node_id].execution_key,
                "structured_result": _safe_value(result.structured_result),
            },
            warnings=list(result.warnings[:8]),
        )

    runtime_registry.register(
        RuntimeHandlerDescriptor(
            handler_id=handler_id,
            kind="provider",
            requires_approval=requires_approval,
            side_effecting=requires_approval,
            replay_safe=not requires_approval,
        ),
        execute,
    )


def register_internal_agent_handler(
    runtime_registry: RuntimeHandlerRegistry,
    internal_agents: Any,
    *,
    handler_id: str = "agent.internal",
) -> None:
    async def execute(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        if not node.target_id:
            raise RuntimeNodeError("internal_agent_target_missing")
        request = _request_input(run, node)
        result = await internal_agents.run(node.target_id, request, None)
        status = (
            RuntimeNodeStatus.PARTIAL
            if result.status == AgentResultStatus.FAILED
            else RuntimeNodeStatus.SUCCEEDED
        )
        return RuntimeObservation(
            node_id=node.node_id,
            terminal_status=status,
            artifact_ids=[item.artifact_id for item in result.artifacts],
            facts={
                "agent_id": result.agent_id,
                "provider": result.provider,
                "result_status": result.status.value,
                "execution_key": run.nodes[node.node_id].execution_key,
                "structured_result": _safe_value(result.structured_result),
            },
            warnings=list(result.warnings[:8]),
        )

    runtime_registry.register(
        RuntimeHandlerDescriptor(
            handler_id=handler_id,
            kind="subagent",
            requires_approval=False,
            replay_safe=True,
        ),
        execute,
    )


def register_subagent_handlers(
    runtime_registry: RuntimeHandlerRegistry,
    internal_agents: Any,
    subagent_registry: RuntimeSubagentRegistry,
    child_run_service: Any | None = None,
    event_hook: Callable[[str, AgentRun, str], Any] | None = None,
) -> list[str]:
    """Register only explicitly declared internal sub-agent capabilities."""

    registered: list[str] = []
    for definition in subagent_registry.list_subagents():
        if not definition.enabled:
            continue
        handler_id = f"subagent.{definition.subagent_id}"

        async def execute(
            run: AgentRun,
            node: RuntimeNode,
            *,
            _definition: RuntimeSubagentDefinition = definition,
        ) -> RuntimeObservation:
            if node.target_id and node.target_id != _definition.target_agent_id:
                raise RuntimeNodeError("subagent_target_policy_mismatch")
            request = _request_input(run, node)
            subagent_run_id = f"{run.run_id}:subagent:{node.node_id}"
            options = dict(request.options)
            options.update(
                {
                    "runtime_execution_key": subagent_run_id,
                    "runtime_parent_run_id": run.run_id,
                    "runtime_subagent_id": _definition.subagent_id,
                    "runtime_subagent_version": _definition.version,
                    "runtime_allow_structured_fallback": True,
                }
            )
            request = request.model_copy(update={"options": options})
            child_run_id = ""
            if child_run_service is not None:
                result, child_run_id = await child_run_service.execute_with_run(
                    run,
                    node,
                    _definition,
                    request,
                    event_hook=event_hook,
                    internal_agents=internal_agents,
                )
            else:
                result = await internal_agents.run(
                    _definition.target_agent_id, request, None
                )
            status = (
                RuntimeNodeStatus.PARTIAL
                if result.status == AgentResultStatus.FAILED
                else RuntimeNodeStatus.SUCCEEDED
            )
            return RuntimeObservation(
                node_id=node.node_id,
                terminal_status=status,
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={
                    "subagent_id": _definition.subagent_id,
                    "target_agent_id": _definition.target_agent_id,
                    "subagent_run_id": subagent_run_id,
                    "child_run_id": child_run_id,
                    "parent_runtime_run_id": run.run_id,
                    "agent_id": result.agent_id,
                    "provider": result.provider,
                    "result_status": result.status.value,
                    "execution_key": run.nodes[node.node_id].execution_key,
                    "structured_result": _safe_value(result.structured_result),
                    "answer": _safe_value(result.answer),
                    "result_payload": result.model_dump(mode="json"),
                },
                warnings=list(result.warnings[:8]),
            )

        runtime_registry.register(
            RuntimeHandlerDescriptor(
                handler_id=handler_id,
                kind="subagent",
                version=definition.version,
                requires_approval=(
                    definition.requires_approval and child_run_service is None
                ),
                side_effecting=definition.side_effecting,
                replay_safe=definition.replay_safe,
                max_timeout_ms=definition.max_timeout_ms,
            ),
            execute,
        )
        registered.append(handler_id)
    return registered


def build_runtime_handler_registry(
    tool_registry: ToolRegistry,
    provider: AgentProvider,
    internal_agents: Any | None = None,
    *,
    subagent_registry: RuntimeSubagentRegistry | None = None,
) -> RuntimeHandlerRegistry:
    registry = RuntimeHandlerRegistry()
    register_tool_handlers(registry, tool_registry)
    register_provider_handler(registry, provider)
    if internal_agents is not None:
        if subagent_registry is None:
            register_internal_agent_handler(registry, internal_agents)
        else:
            register_subagent_handlers(registry, internal_agents, subagent_registry)
    return registry
