"""Provider-free capability descriptors for the two Runtime entry points.

This module is deliberately an inspection-only adapter.  It reads stable
class/instance attributes from Runtime services and never invokes a business
service, Provider, request validator, or execution method.  The descriptor is
immutable so it can be safely projected into readiness and operator views in
later migration slices.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.services.runtime_business_registry import RuntimeBusinessService
from app.services.runtime_control_policy import control_policy_for_runtime_kind

CapabilityDomain = Literal["task_agent", "learning_loop"]

TASK_RUNTIME_ACTIONS: tuple[str, ...] = (
    "observe",
    "decide",
    "act",
    "verify",
    "replan",
)
TEACHING_INTERACTION_ACTIONS: tuple[str, ...] = (
    "request_more_hint",
    "submit_check_response",
    "switch_to_direct_answer",
)
LEARNING_PROGRESS_ACTIONS: tuple[str, ...] = (
    "submit_attempt_revision",
    "start_retest",
    "complete_retest",
    "dismiss_retest",
)


class _LearningRuntimeService(Protocol):
    """Minimal attribute-only shape used by the learning adapters."""

    agent_id: str
    agent_version: str
    run_kind: str
    plan_version: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityDescriptor:
    """Immutable, provider-free description of one Runtime capability.

    ``supported_actions`` is a tuple rather than a mutable list.  The
    ``control_scope`` value identifies the owner of lifecycle controls and is
    intentionally separate from the input/result contracts: sharing the
    Runtime kernel does not merge Task and LearningLoop request protocols.
    """

    capability_id: str
    domain: CapabilityDomain
    runtime_id: str
    version: str
    enabled: bool
    supported_actions: tuple[str, ...]
    supports_pause: bool
    supports_resume: bool
    supports_approval: bool
    supports_input: bool
    result_contract: str
    control_scope: str
    # Optional for backwards-compatible construction of descriptors created
    # before capability identity was exposed.  Learning services declare this
    # explicitly; an empty value must remain visible so readiness can fail
    # closed rather than infer an identity from an artifact or plan version.
    agent_version: str = ""

    def __post_init__(self) -> None:
        if self.domain not in {"task_agent", "learning_loop"}:
            raise ValueError(f"unsupported capability domain: {self.domain}")
        for field_name in (
            "capability_id",
            "runtime_id",
            "version",
            "result_contract",
            "control_scope",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")

        normalized_actions = _normalize_tokens(self.supported_actions)
        if not normalized_actions:
            raise ValueError("supported_actions must not be empty")
        object.__setattr__(self, "supported_actions", normalized_actions)
        object.__setattr__(self, "capability_id", self.capability_id.strip())
        object.__setattr__(self, "runtime_id", self.runtime_id.strip())
        object.__setattr__(self, "version", self.version.strip())
        object.__setattr__(self, "agent_version", self.agent_version.strip())
        object.__setattr__(self, "result_contract", self.result_contract.strip())
        object.__setattr__(self, "control_scope", self.control_scope.strip())

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-safe projection without exposing services."""

        return {
            "capability_id": self.capability_id,
            "domain": self.domain,
            "runtime_id": self.runtime_id,
            "version": self.version,
            "agent_version": self.agent_version,
            "enabled": self.enabled,
            "supported_actions": list(self.supported_actions),
            "supports_pause": self.supports_pause,
            "supports_resume": self.supports_resume,
            "supports_approval": self.supports_approval,
            "supports_input": self.supports_input,
            "result_contract": self.result_contract,
            "control_scope": self.control_scope,
        }


def descriptor_from_task_runtime_service(
    service: RuntimeBusinessService,
) -> RuntimeCapabilityDescriptor:
    """Build a descriptor from a Task ``RuntimeBusinessService`` by inspection.

    The default control declaration reflects the existing Task Runtime
    control surface.  Services can narrow it by declaring the corresponding
    boolean attributes; this adapter never assumes that an optional method is
    executable merely because it exists.
    """

    capability_id = _required_text(service, "agent_id")
    runtime_id = _first_text(
        service,
        "runtime_id",
        "runtime_option_key",
        "run_kind",
        default=capability_id,
    )
    version = _first_text(
        service,
        "runtime_plan_version",
        "plan_version",
        "version",
        default="unversioned",
    )
    control_scope = _first_text(
        service, "control_scope", default="task_runtime"
    )
    control_policy = control_policy_for_runtime_kind(control_scope)
    return RuntimeCapabilityDescriptor(
        capability_id=_first_text(service, "capability_id", default=capability_id),
        domain="task_agent",
        runtime_id=runtime_id,
        version=version,
        agent_version=_first_text(service, "agent_version", default=""),
        enabled=_read_bool(service, "enabled", default=False),
        supported_actions=_read_actions(
            service, default=TASK_RUNTIME_ACTIONS
        ),
        supports_pause=_read_bool(
            service,
            "supports_pause",
            default="pause" in control_policy.declared_controls,
        ),
        supports_resume=_read_bool(
            service,
            "supports_resume",
            default="resume" in control_policy.declared_controls,
        ),
        supports_approval=_read_bool(
            service,
            "supports_approval",
            default="approve" in control_policy.declared_controls,
        ),
        supports_input=_read_bool(
            service,
            "supports_input",
            default="input" in control_policy.declared_controls,
        ),
        result_contract=_first_text(
            service, "result_contract", default="agent_result.v1"
        ),
        control_scope=control_scope,
    )


def descriptor_from_teaching_interaction_runtime_service(
    service: _LearningRuntimeService,
) -> RuntimeCapabilityDescriptor:
    """Describe ``TeachingInteractionRuntimeService`` without adapting input."""

    return _descriptor_from_learning_service(
        service,
        default_actions=TEACHING_INTERACTION_ACTIONS,
    )


def descriptor_from_learning_progress_runtime_service(
    service: _LearningRuntimeService,
) -> RuntimeCapabilityDescriptor:
    """Describe ``LearningProgressRuntimeService`` without adapting input."""

    return _descriptor_from_learning_service(
        service,
        default_actions=LEARNING_PROGRESS_ACTIONS,
    )


def descriptors_from_learning_loop_services(
    *,
    teaching_interaction: _LearningRuntimeService | None = None,
    learning_progress: _LearningRuntimeService | None = None,
) -> tuple[RuntimeCapabilityDescriptor, ...]:
    """Build the available learning descriptors in deterministic order."""

    descriptors: list[RuntimeCapabilityDescriptor] = []
    if teaching_interaction is not None:
        descriptors.append(
            descriptor_from_teaching_interaction_runtime_service(
                teaching_interaction
            )
        )
    if learning_progress is not None:
        descriptors.append(
            descriptor_from_learning_progress_runtime_service(learning_progress)
        )
    return tuple(descriptors)


def descriptors_from_task_runtime_services(
    services: Iterable[RuntimeBusinessService],
) -> tuple[RuntimeCapabilityDescriptor, ...]:
    """Build Task descriptors while preserving registry order."""

    return tuple(descriptor_from_task_runtime_service(service) for service in services)


def _descriptor_from_learning_service(
    service: _LearningRuntimeService,
    *,
    default_actions: tuple[str, ...],
) -> RuntimeCapabilityDescriptor:
    capability_id = _required_text(service, "agent_id")
    control_scope = _first_text(
        service, "control_scope", default="learning_loop"
    )
    control_policy = control_policy_for_runtime_kind(control_scope)
    return RuntimeCapabilityDescriptor(
        capability_id=_first_text(service, "capability_id", default=capability_id),
        domain="learning_loop",
        runtime_id=_first_text(
            service, "runtime_id", "run_kind", default=capability_id
        ),
        version=_first_text(
            service,
            "runtime_plan_version",
            "plan_version",
            "version",
            default="unversioned",
        ),
        agent_version=_first_text(service, "agent_version", default=""),
        enabled=_read_bool(service, "enabled", default=False),
        supported_actions=_read_actions(service, default=default_actions),
        # LearningLoop exposes the same durable control vocabulary as the
        # shared Runtime policy; the status-aware API still decides which
        # action is available for a particular checkpoint.
        supports_pause=_read_bool(
            service,
            "supports_pause",
            default="pause" in control_policy.declared_controls,
        ),
        supports_resume=_read_bool(
            service,
            "supports_resume",
            default="resume" in control_policy.declared_controls,
        ),
        supports_approval=_read_bool(
            service,
            "supports_approval",
            default="approve" in control_policy.declared_controls,
        ),
        supports_input=_read_bool(
            service,
            "supports_input",
            default="input" in control_policy.declared_controls,
        ),
        result_contract=_first_text(
            service, "result_contract", default="learning_action_response.v1"
        ),
        control_scope=control_scope,
    )


def _required_text(service: object, attribute: str) -> str:
    value = getattr(service, attribute, None)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"service.{attribute} must be a non-empty string")
    return value.strip()


def _first_text(
    service: object,
    *attributes: str,
    default: str,
) -> str:
    for attribute in attributes:
        value = getattr(service, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _read_bool(service: object, attribute: str, *, default: bool) -> bool:
    value = getattr(service, attribute, None)
    return value if isinstance(value, bool) else default


def _read_actions(
    service: object,
    *,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    value = getattr(service, "supported_actions", None)
    if isinstance(value, str):
        return _normalize_tokens((value,))
    if isinstance(value, Iterable):
        return _normalize_tokens(value)
    return default


def _normalize_tokens(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        token = value.strip()
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)


__all__ = [
    "CapabilityDomain",
    "LEARNING_PROGRESS_ACTIONS",
    "TASK_RUNTIME_ACTIONS",
    "TEACHING_INTERACTION_ACTIONS",
    "RuntimeCapabilityDescriptor",
    "descriptor_from_learning_progress_runtime_service",
    "descriptor_from_task_runtime_service",
    "descriptor_from_teaching_interaction_runtime_service",
    "descriptors_from_learning_loop_services",
    "descriptors_from_task_runtime_services",
]
