from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest
from app.contracts import AgentRequest
from app.contracts.learning import LearningActionRequest
from app.services.learning_progress_runtime import LearningProgressRuntimeService
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.runtime_capability_descriptor import (
    LEARNING_PROGRESS_ACTIONS,
    TASK_RUNTIME_ACTIONS,
    TEACHING_INTERACTION_ACTIONS,
    RuntimeCapabilityDescriptor,
    descriptor_from_learning_progress_runtime_service,
    descriptor_from_task_runtime_service,
    descriptor_from_teaching_interaction_runtime_service,
    descriptors_from_learning_loop_services,
    descriptors_from_task_runtime_services,
)
from app.services.teaching_interaction_runtime import (
    TeachingInteractionRuntimeService,
)


class ExplodingTaskService:
    agent_id = "TASK_AGENT_V1"
    runtime_option_key = "task_runtime"
    runtime_plan_version = "task-runtime-v1"
    enabled = True
    supported_actions: list[str]

    def supports(self, *_args: object, **_kwargs: object) -> bool:
        raise AssertionError("descriptor inspection must not call supports")

    def build_plan(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("descriptor inspection must not call build_plan")

    async def run(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("descriptor inspection must not call run")


class TeachingService:
    agent_id = "TEACHING_INTERACTION_V1"
    run_kind = "teaching_interaction"
    plan_version = "teaching-interaction-v1"
    enabled = True


class DisabledProgressService:
    agent_id = "LEARNING_PROGRESS_V1"
    run_kind = "learning_progress"
    plan_version = "learning-progress-v1"
    enabled = False


def test_task_descriptor_has_stable_fields_and_is_provider_free() -> None:
    descriptor = descriptor_from_task_runtime_service(ExplodingTaskService())  # type: ignore[arg-type]

    assert descriptor == RuntimeCapabilityDescriptor(
        capability_id="TASK_AGENT_V1",
        domain="task_agent",
        runtime_id="task_runtime",
        version="task-runtime-v1",
        enabled=True,
        supported_actions=TASK_RUNTIME_ACTIONS,
        supports_pause=True,
        supports_resume=True,
        supports_approval=True,
        supports_input=True,
        result_contract="agent_result.v1",
        control_scope="task_runtime",
    )
    assert descriptor.to_dict()["supported_actions"] == list(TASK_RUNTIME_ACTIONS)
    assert descriptor.agent_version == ""
    assert descriptor.to_dict()["agent_version"] == ""
    with pytest.raises(FrozenInstanceError):
        descriptor.enabled = False  # type: ignore[misc]


def test_learning_descriptor_preserves_learning_boundary() -> None:
    descriptor = descriptor_from_teaching_interaction_runtime_service(
        TeachingService()  # type: ignore[arg-type]
    )

    assert descriptor.domain == "learning_loop"
    assert descriptor.runtime_id == "teaching_interaction"
    assert descriptor.version == "teaching-interaction-v1"
    assert descriptor.agent_version == ""
    assert descriptor.supported_actions == TEACHING_INTERACTION_ACTIONS
    assert descriptor.supports_pause is True
    assert descriptor.supports_resume is True
    assert descriptor.supports_approval is True
    assert descriptor.supports_input is True
    assert descriptor.result_contract == "learning_action_response.v1"
    assert descriptor.control_scope == "learning_loop"

    request = LearningActionRequest(
        source_task_id="task-1",
        user_id="user-1",
        action="request_more_hint",
        idempotency_key="idempotency-1",
    )
    assert isinstance(request, LearningActionRequest)
    assert not isinstance(request, AgentRequest)


def test_learning_factory_order_and_disabled_state_are_read_only() -> None:
    disabled = descriptor_from_learning_progress_runtime_service(
        DisabledProgressService()  # type: ignore[arg-type]
    )
    descriptors = descriptors_from_learning_loop_services(
        teaching_interaction=TeachingService(),  # type: ignore[arg-type]
        learning_progress=DisabledProgressService(),  # type: ignore[arg-type]
    )

    assert disabled.enabled is False
    assert disabled.supported_actions == LEARNING_PROGRESS_ACTIONS
    assert [item.capability_id for item in descriptors] == [
        "TEACHING_INTERACTION_V1",
        "LEARNING_PROGRESS_V1",
    ]
    assert descriptors[1].enabled is False


def test_declared_actions_are_deduplicated_without_calling_service_methods() -> None:
    service = ExplodingTaskService()
    service.supported_actions = [" verify ", "verify", "act"]

    descriptor = descriptor_from_task_runtime_service(service)  # type: ignore[arg-type]

    assert descriptor.supported_actions == ("verify", "act")


def test_task_descriptor_can_bind_authoritative_registry_version() -> None:
    descriptors = descriptors_from_task_runtime_services(
        [ExplodingTaskService()],
        agent_versions={"TASK_AGENT_V1": "2.3"},
    )

    assert len(descriptors) == 1
    assert descriptors[0].agent_version == "2.3"
    assert descriptors[0].to_dict()["agent_version"] == "2.3"


def test_real_learning_runtime_services_declare_agent_version() -> None:
    teaching = TeachingInteractionRuntimeService(
        cast(Any, object()), enabled=True
    )
    progress = LearningProgressRuntimeService(cast(Any, object()), enabled=True)

    descriptors = descriptors_from_learning_loop_services(
        teaching_interaction=teaching,
        learning_progress=progress,
    )

    assert [descriptor.agent_version for descriptor in descriptors] == [
        "learning-agent-v1",
        "learning-agent-v1",
    ]
    assert [descriptor.to_dict()["agent_version"] for descriptor in descriptors] == [
        "learning-agent-v1",
        "learning-agent-v1",
    ]


def test_research_analysis_runtime_declares_stable_plan_version() -> None:
    service = ResearchAnalysisRuntimeService(cast(Any, object()), enabled=True)

    descriptor = descriptor_from_task_runtime_service(
        service, agent_version="1.0"
    )

    assert descriptor.capability_id == "RESEARCH_03_DATA_ANALYSIS_V1"
    assert descriptor.version == "research-v2"
    assert descriptor.agent_version == "1.0"
