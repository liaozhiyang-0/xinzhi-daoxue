"""Typed, bounded registrations for Runtime sub-agent calls.

The legacy internal-agent adapter accepts a target at execution time.  The
Runtime needs a stronger boundary: a plan may call only a sub-agent that was
declared by the application, with an explicit version and execution policy.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RuntimeSubagentDefinition(BaseModel):
    """Policy and target metadata for one Runtime sub-agent capability."""

    model_config = ConfigDict(extra="forbid")

    subagent_id: str = Field(min_length=1, max_length=120)
    target_agent_id: str = Field(min_length=1, max_length=160)
    version: str = Field(default="1", min_length=1, max_length=32)
    enabled: bool = True
    requires_approval: bool = False
    side_effecting: bool = False
    replay_safe: bool = True
    max_timeout_ms: int = Field(default=120_000, ge=100, le=900_000)


class RuntimeSubagentRegistryError(RuntimeError):
    """Raised when a declared Runtime sub-agent cannot be resolved."""

    def __init__(self, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code


class RuntimeSubagentRegistry:
    """Validated registry of sub-agents callable by declarative plans."""

    def __init__(self) -> None:
        self._definitions: dict[str, RuntimeSubagentDefinition] = {}
        self._frozen = False

    def register(self, definition: RuntimeSubagentDefinition) -> None:
        if self._frozen:
            raise RuntimeSubagentRegistryError(
                "registry_frozen",
                "runtime sub-agent registry is frozen",
            )
        if definition.subagent_id in self._definitions:
            raise ValueError(
                f"runtime sub-agent already registered: {definition.subagent_id}"
            )
        self._definitions[definition.subagent_id] = definition

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def describe(self, subagent_id: str) -> RuntimeSubagentDefinition:
        definition = self._definitions.get(subagent_id)
        if definition is None:
            raise RuntimeSubagentRegistryError(
                "subagent_not_registered",
                f"runtime sub-agent is not registered: {subagent_id}",
            )
        return definition

    def list_subagents(self) -> tuple[RuntimeSubagentDefinition, ...]:
        return tuple(self._definitions.values())
