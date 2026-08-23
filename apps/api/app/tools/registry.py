from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.circuit.tool import circuit_render_tool
from app.tools.calculator import calculate
from app.tools.sympy_solver import solve_equations
from app.tools.unit_checker import check_unit_compatibility


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    tool_id: str
    name: str
    supported_capabilities: frozenset[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_seconds: float = 10
    side_effect_level: str = "none"
    requires_sandbox: bool = False
    enabled: bool = True
    deterministic: bool = True


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: Callable[..., Any] | None


class ToolRegistry:
    """The only runtime tool registry, including execution policy metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        definition: ToolDefinition | str,
        handler: Callable[..., Any] | None = None,
    ) -> None:
        if isinstance(definition, str):
            definition = ToolDefinition(definition, definition, frozenset(), {}, {})
        if not definition.tool_id or definition.tool_id in self._tools:
            raise ValueError(f"工具名称无效或重复: {definition.tool_id}")
        if definition.enabled and handler is None:
            raise ValueError(f"启用的工具必须提供 handler: {definition.tool_id}")
        self._tools[definition.tool_id] = RegisteredTool(definition, handler)

    def get(self, name: str) -> Callable[..., Any]:
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"未注册工具: {name}") from exc
        if not tool.definition.enabled or tool.handler is None:
            raise RuntimeError(f"工具当前未启用: {name}")
        return tool.handler

    def describe(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name].definition
        except KeyError as exc:
            raise KeyError(f"未注册工具: {name}") from exc

    def list_tools(self) -> list[ToolDefinition]:
        return [self._tools[key].definition for key in sorted(self._tools)]

    def capabilities(self) -> list[str]:
        return sorted(self._tools)


def default_tool_registry(*, circuit_render_enabled: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    active: dict[str, tuple[Callable[..., Any], set[str]]] = {
        "calculator": (calculate, {"algebra", "complex_numbers"}),
        "sympy_solver": (
            solve_equations,
            {"algebra", "calculus", "equation_system", "differential_equations"},
        ),
        "linear_equation_solver": (solve_equations, {"equation_system"}),
        "complex_number_tool": (calculate, {"complex_numbers"}),
        "unit_checker": (check_unit_compatibility, {"unit_validation"}),
    }
    for tool_id, (handler, capabilities) in active.items():
        registry.register(
            ToolDefinition(
                tool_id,
                tool_id,
                frozenset(capabilities),
                {"type": "object"},
                {"type": "object"},
            ),
            handler,
        )
    for tool_id, capabilities, requires_sandbox in (
        ("plotting_tool", {"plotting"}, False),
        ("python_executor", {"code_analysis"}, True),
        ("boolean_simplifier", {"boolean_algebra"}, False),
        ("truth_table_generator", {"logic_analysis", "state_machine"}, False),
        ("signal_transform_tool", {"signal_transform"}, False),
        ("hdl_static_analyzer", {"hdl_analysis"}, True),
    ):
        registry.register(
            ToolDefinition(
                tool_id,
                tool_id,
                frozenset(capabilities),
                {"type": "object"},
                {"type": "object"},
                requires_sandbox=requires_sandbox,
                enabled=False,
            )
        )
    registry.register(
        ToolDefinition(
            "circuit.render",
            "CircuitIR SVG renderer",
            frozenset({"circuit_render"}),
            {"type": "object", "required": ["circuit"]},
            {"type": "object", "required": ["status", "validation_state", "warnings"]},
            timeout_seconds=10,
            side_effect_level="none",
            requires_sandbox=False,
            enabled=circuit_render_enabled,
            deterministic=True,
        ),
        circuit_render_tool if circuit_render_enabled else None,
    )
    return registry
