from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.contracts import AgentRun, RuntimeNode, RuntimeObservation

RuntimeNodeHandler = Callable[
    [AgentRun, RuntimeNode], RuntimeObservation | Awaitable[RuntimeObservation]
]
RuntimeHandlerKind = Literal["tool", "agent", "provider", "subagent", "workflow"]


class RuntimeHandlerDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handler_id: str = Field(min_length=1, max_length=160)
    kind: RuntimeHandlerKind
    version: str = Field(default="1", min_length=1, max_length=32)
    enabled: bool = True
    requires_approval: bool = False
    side_effecting: bool = False
    replay_safe: bool = True
    max_timeout_ms: int = Field(default=900_000, ge=100, le=900_000)


class RuntimeHandlerRegistryError(RuntimeError):
    def __init__(self, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class _Registration:
    descriptor: RuntimeHandlerDescriptor
    handler: RuntimeNodeHandler


class RuntimeHandlerRegistry:
    """Validated registry for executable Runtime handlers."""

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}

    def register(
        self,
        descriptor: RuntimeHandlerDescriptor,
        handler: RuntimeNodeHandler,
    ) -> None:
        if descriptor.handler_id in self._registrations:
            raise ValueError(
                f"runtime handler already registered: {descriptor.handler_id}"
            )
        self._registrations[descriptor.handler_id] = _Registration(
            descriptor=descriptor,
            handler=handler,
        )

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

    def descriptors(self) -> list[RuntimeHandlerDescriptor]:
        return [
            registration.descriptor
            for registration in self._registrations.values()
        ]
