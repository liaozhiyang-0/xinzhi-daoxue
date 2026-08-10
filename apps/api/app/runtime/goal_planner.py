"""Bounded goal-to-plan compilation over registered Runtime capabilities."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.contracts import AgentRunPlan, RuntimeGoal, RuntimeNode
from app.runtime.handler_registry import (
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
)


class RuntimeGoalPlannerError(ValueError):
    """Raised when a structured goal cannot be compiled safely."""


class RuntimeCapabilitySelection(BaseModel):
    """Audit facts for one capability selected into a Runtime plan."""

    model_config = ConfigDict(extra="forbid")

    capability: str = Field(min_length=1, max_length=160)
    handler_id: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=32)
    requires_approval: bool = False
    side_effecting: bool = False


class RuntimeGoalPlanResult(BaseModel):
    """Plan plus bounded selection evidence, without model/provider calls."""

    model_config = ConfigDict(extra="forbid")

    plan: AgentRunPlan
    selections: list[RuntimeCapabilitySelection] = Field(
        min_length=1, max_length=100
    )
    requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class _CapabilityCandidate:
    capability: str
    descriptor: RuntimeHandlerDescriptor


class RuntimeGoalPlanner:
    """Compile structured capabilities into executable, registered nodes."""

    def __init__(self, registry: RuntimeHandlerRegistry) -> None:
        self._registry = registry

    def build(
        self,
        goal: RuntimeGoal,
        *,
        plan_id: str,
        version: str = "goal-v1",
        max_parallelism: int = 1,
    ) -> RuntimeGoalPlanResult:
        if not goal.required_capabilities:
            raise RuntimeGoalPlannerError("goal_has_no_required_capabilities")

        # Runtime handlers can be registered by an enabled extension after the
        # TaskRunner is constructed. Build the bounded alias index per plan so
        # an explicit goal sees the current registry rather than a stale
        # startup snapshot.
        candidates = self._index(self._registry.descriptors())
        nodes: list[RuntimeNode] = []
        selections: list[RuntimeCapabilitySelection] = []
        phases = _execution_phases(goal)
        previous_node_ids: list[str] = []
        step = 0
        for phase_index, phase in enumerate(phases, start=1):
            phase_node_ids: list[str] = []
            for capability in phase:
                step += 1
                candidate = candidates.get(capability.casefold())
                if candidate is None:
                    raise RuntimeGoalPlannerError(
                        f"capability_not_registered:{capability}"
                    )
                node_id = f"goal.step.{step}.{_safe_id(capability)}"
                node = RuntimeNode(
                    node_id=node_id,
                    node_type=candidate.descriptor.kind,
                    handler_id=candidate.descriptor.handler_id,
                    timeout_ms=min(
                        900_000,
                        max(100, candidate.descriptor.max_timeout_ms),
                    ),
                    depends_on=list(previous_node_ids),
                    parallel_group=(
                        f"goal.phase.{phase_index}" if len(phase) > 1 else ""
                    ),
                )
                nodes.append(node)
                selections.append(
                    RuntimeCapabilitySelection(
                        capability=capability,
                        handler_id=candidate.descriptor.handler_id,
                        kind=candidate.descriptor.kind,
                        requires_approval=candidate.descriptor.requires_approval,
                        side_effecting=candidate.descriptor.side_effecting,
                    )
                )
                phase_node_ids.append(node_id)
            previous_node_ids.extend(phase_node_ids)

        plan = AgentRunPlan(
            plan_id=plan_id,
            version=version,
            goal=goal.objective,
            goal_contract=goal,
            nodes=nodes,
            success_criteria=list(goal.success_criteria),
            max_parallelism=max(1, min(32, max_parallelism)),
        )
        return RuntimeGoalPlanResult(
            plan=plan,
            selections=selections,
            requires_approval=any(
                selection.requires_approval for selection in selections
            ),
        )

    @staticmethod
    def _index(
        descriptors: list[RuntimeHandlerDescriptor],
    ) -> dict[str, _CapabilityCandidate]:
        candidates: dict[str, _CapabilityCandidate] = {}
        for descriptor in descriptors:
            if not descriptor.enabled:
                continue
            aliases = {descriptor.handler_id.casefold()}
            prefix, separator, short_id = descriptor.handler_id.partition(".")
            if separator and short_id:
                aliases.add(short_id.casefold())
            candidate = _CapabilityCandidate(
                capability=descriptor.handler_id,
                descriptor=descriptor,
            )
            for alias in aliases:
                existing = candidates.get(alias)
                if existing is not None and existing.descriptor.handler_id != (
                    descriptor.handler_id
                ):
                    # Ambiguous short aliases are deliberately removed; callers
                    # can still select either capability using its full ID.
                    candidates.pop(alias, None)
                    continue
                candidates[alias] = candidate
        return candidates


def _safe_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return normalized[:80] or "capability"


def _execution_phases(goal: RuntimeGoal) -> list[list[str]]:
    """Resolve explicit independent batches without guessing dependencies."""

    required = [item.strip() for item in goal.required_capabilities]
    if any(not item for item in required):
        raise RuntimeGoalPlannerError("goal_contains_empty_capability")
    required_keys = [item.casefold() for item in required]
    if len(required_keys) != len(set(required_keys)):
        raise RuntimeGoalPlannerError("goal_contains_duplicate_capability")
    if not goal.parallel_groups:
        return [[item] for item in required]

    required_by_key = dict(zip(required_keys, required, strict=True))
    seen: set[str] = set()
    phases: list[list[str]] = []
    for group in goal.parallel_groups:
        if not group:
            raise RuntimeGoalPlannerError("parallel_group_empty")
        phase: list[str] = []
        for item in group:
            normalized = item.strip()
            if not normalized:
                raise RuntimeGoalPlannerError(
                    "parallel_group_contains_empty_capability"
                )
            key = normalized.casefold()
            if key not in required_by_key:
                raise RuntimeGoalPlannerError(
                    f"parallel_capability_not_required:{normalized}"
                )
            if key in seen:
                raise RuntimeGoalPlannerError(
                    f"parallel_capability_duplicate:{normalized}"
                )
            seen.add(key)
            phase.append(required_by_key[key])
        phases.append(phase)
    missing = [required_by_key[key] for key in required_keys if key not in seen]
    if missing:
        raise RuntimeGoalPlannerError(
            "parallel_capability_missing:" + ",".join(missing)
        )
    return phases
