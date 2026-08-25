from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.contracts import AgentRun, RuntimeNode, RuntimeObservation

RuntimeNodeHandler = Callable[
    [AgentRun, RuntimeNode], RuntimeObservation | Awaitable[RuntimeObservation]
]
RuntimeHandlerKind = Literal["tool", "agent", "provider", "subagent", "workflow"]
RuntimeRiskLevel = Literal["low", "medium", "high", "critical"]


class RuntimeHandlerDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handler_id: str = Field(min_length=1, max_length=160)
    kind: RuntimeHandlerKind
    version: str = Field(default="1", min_length=1, max_length=32)
    enabled: bool = True
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    permission_scope: str = Field(
        default="runtime",
        min_length=1,
        max_length=160,
    )
    side_effect_level: str = Field(default="none", min_length=1, max_length=32)
    requires_sandbox: bool = False
    risk_level: RuntimeRiskLevel = "low"
    requires_approval: bool = False
    side_effecting: bool = False
    replay_safe: bool = True
    max_timeout_ms: int = Field(default=900_000, ge=100, le=900_000)


class RuntimeHandlerRegistryError(RuntimeError):
    def __init__(self, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code


_SUPPORTED_INPUT_SCHEMA_KEYS = frozenset(
    {"type", "required", "properties", "additionalProperties"}
)
_SUPPORTED_INPUT_TYPES = frozenset(
    {"string", "number", "integer", "boolean", "array", "null", "object"}
)


def _schema_error(error_code: str, path: str, message: str) -> None:
    raise RuntimeHandlerRegistryError(error_code, f"{path}: {message}")


def _matches_type(value: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(value, Mapping)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "null":
        return value is None
    return False


def validate_input_schema(
    value: Any,
    schema: Mapping[str, Any] | None,
    *,
    path: str = "$",
) -> None:
    """Validate the provider-free input-schema subset used by Runtime tools.

    The supported subset intentionally stops at object/type, required,
    properties, additionalProperties, and the JSON primitive/container types.
    An empty or missing schema imposes no additional restriction. Output
    schemas are descriptive only and are deliberately not validated here.
    """

    if not schema:
        return
    if not isinstance(schema, Mapping):
        _schema_error("handler_input_schema_invalid", path, "schema must be an object")
    unsupported = set(schema) - _SUPPORTED_INPUT_SCHEMA_KEYS
    if unsupported:
        _schema_error(
            "handler_input_schema_unsupported",
            path,
            f"unsupported keywords: {sorted(unsupported)}",
        )

    schema_type = schema.get("type")
    if schema_type is not None:
        if (
            not isinstance(schema_type, str)
            or schema_type not in _SUPPORTED_INPUT_TYPES
        ):
            _schema_error(
                "handler_input_schema_invalid",
                path,
                f"unsupported type: {schema_type!r}",
            )
        if not _matches_type(value, schema_type):
            _schema_error(
                "node_input_schema_type_mismatch",
                path,
                f"expected {schema_type}",
            )

    required = schema.get("required", [])
    if not isinstance(required, list) or not all(
        isinstance(item, str) for item in required
    ):
        _schema_error(
            "handler_input_schema_invalid",
            path,
            "required must be a list of strings",
        )
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping) or not all(
        isinstance(key, str) and isinstance(item, Mapping)
        for key, item in properties.items()
    ):
        _schema_error(
            "handler_input_schema_invalid",
            path,
            "properties must map strings to schema objects",
        )
    additional_properties = schema.get("additionalProperties", True)
    if not isinstance(additional_properties, bool):
        _schema_error(
            "handler_input_schema_invalid",
            path,
            "additionalProperties must be boolean",
        )

    if not isinstance(value, Mapping):
        return
    missing = [key for key in required if key not in value]
    if missing:
        _schema_error(
            "node_input_schema_required",
            path,
            f"missing required properties: {missing}",
        )
    if not additional_properties:
        unexpected = sorted(set(value) - set(properties))
        if unexpected:
            _schema_error(
                "node_input_schema_additional_property",
                path,
                f"additional properties are not allowed: {unexpected}",
            )
    for key, property_schema in properties.items():
        if key in value:
            validate_input_schema(
                value[key], property_schema, path=f"{path}.{key}"
            )


@dataclass(frozen=True)
class _Registration:
    descriptor: RuntimeHandlerDescriptor
    handler: RuntimeNodeHandler


class RuntimeHandlerRegistry:
    """Validated registry for executable Runtime handlers."""

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._frozen = False

    def register(
        self,
        descriptor: RuntimeHandlerDescriptor,
        handler: RuntimeNodeHandler,
    ) -> None:
        if self._frozen:
            raise RuntimeHandlerRegistryError(
                "registry_frozen",
                "runtime handler registry is frozen",
            )
        if descriptor.handler_id in self._registrations:
            raise ValueError(
                f"runtime handler already registered: {descriptor.handler_id}"
            )
        self._registrations[descriptor.handler_id] = _Registration(
            descriptor=descriptor,
            handler=handler,
        )

    def freeze(self) -> None:
        """Prevent runtime drift after the executable graph is assembled."""

        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def resolve(self, node: RuntimeNode) -> RuntimeNodeHandler:
        registration = self._registrations.get(node.handler_id)
        if registration is None:
            raise RuntimeHandlerRegistryError(
                "handler_not_registered",
                f"runtime handler is not registered: {node.handler_id}",
            )
        descriptor = registration.descriptor
        if not descriptor.enabled:
            raise RuntimeHandlerRegistryError(
                "handler_disabled",
                f"runtime handler is disabled: {node.handler_id}",
            )
        if node.timeout_ms > descriptor.max_timeout_ms:
            raise RuntimeHandlerRegistryError(
                "handler_timeout_policy_exceeded",
                f"runtime node timeout exceeds handler policy: {node.handler_id}",
            )
        return registration.handler

    def descriptor(self, handler_id: str) -> RuntimeHandlerDescriptor:
        registration = self._registrations.get(handler_id)
        if registration is None:
            raise RuntimeHandlerRegistryError(
                "handler_not_registered",
                f"runtime handler is not registered: {handler_id}",
            )
        return registration.descriptor

    def validate_input(self, handler_id: str, payload: Mapping[str, Any]) -> None:
        """Validate a handler payload before its callable is invoked."""

        descriptor = self.descriptor(handler_id)
        validate_input_schema(payload, descriptor.input_schema)

    def descriptors(self) -> list[RuntimeHandlerDescriptor]:
        return [
            registration.descriptor
            for registration in self._registrations.values()
        ]
