"""Policy gate for turning a structured request goal into Runtime work."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.runtime import RuntimeCapabilitySelection, RuntimeGoal


class RuntimeGoalIntakeError(ValueError):
    """Raised when a goal asks for capabilities outside Agent policy."""


class RuntimeGoalIntakeEvidence(BaseModel):
    """Durable, non-sensitive evidence describing an intake decision."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=160)
    policy_source: str = Field(min_length=1, max_length=64)
    handler_ids: list[str] = Field(min_length=1, max_length=32)
    requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeGoalIntakePolicy:
    """Allow read-only tools by default and gate everything else explicitly.

    ``configured_allowlist`` uses the form
    ``AGENT_ID=handler.one|handler.two;OTHER_AGENT=handler.three``.
    Full registered handler IDs are required so ambiguous short aliases cannot
    accidentally widen an Agent's authority.
    """

    configured_allowlist: dict[str, frozenset[str]]

    @classmethod
    def from_config(cls, value: str) -> RuntimeGoalIntakePolicy:
        entries: dict[str, frozenset[str]] = {}
        for raw_entry in value.split(";"):
            entry = raw_entry.strip()
            if not entry:
                continue
            agent_id, separator, raw_handlers = entry.partition("=")
            if not separator or not agent_id.strip():
                raise ValueError(
                    "AGENT_RUNTIME_GOAL_CAPABILITIES entries must be "
                    "AGENT_ID=handler.one|handler.two"
                )
            normalized_agent = agent_id.strip()
            if normalized_agent in entries:
                raise ValueError(
                    f"duplicate Runtime goal capability policy for "
                    f"{normalized_agent}"
                )
            handlers = frozenset(
                item.strip()
                for item in raw_handlers.split("|")
                if item.strip()
            )
            if not handlers:
                raise ValueError(
                    f"Runtime goal capability policy for {normalized_agent} "
                    "must contain at least one handler ID"
                )
            entries[normalized_agent] = handlers
        return cls(entries)

    def validate(
        self,
        agent_id: str,
        goal: RuntimeGoal,
        selections: list[RuntimeCapabilitySelection],
    ) -> RuntimeGoalIntakeEvidence:
        if not goal.objective.strip():
            raise RuntimeGoalIntakeError("goal_objective_empty")
        if len(selections) > 16:
            raise RuntimeGoalIntakeError("goal_capability_count_exceeded")

        configured = self.configured_allowlist.get(agent_id)
        if configured is not None:
            unauthorized = [
                selection.handler_id
                for selection in selections
                if selection.handler_id not in configured
            ]
            if unauthorized:
                raise RuntimeGoalIntakeError(
                    "goal_capability_not_allowed:" + ",".join(unauthorized)
                )
            policy_source = "agent_allowlist"
        else:
            unsafe = [
                selection.handler_id
                for selection in selections
                if selection.kind != "tool" or selection.side_effecting
            ]
            if unsafe:
                raise RuntimeGoalIntakeError(
                    "goal_capability_requires_agent_allowlist:"
                    + ",".join(unsafe)
                )
            policy_source = "default_read_only_tools"

        return RuntimeGoalIntakeEvidence(
            agent_id=agent_id,
            policy_source=policy_source,
            handler_ids=[selection.handler_id for selection in selections],
            requires_approval=any(
                selection.requires_approval for selection in selections
            ),
        )
