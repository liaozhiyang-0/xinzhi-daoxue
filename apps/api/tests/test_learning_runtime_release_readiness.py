from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from app.services.learning_progress_runtime import LearningProgressRuntimeService
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_capability_descriptor import (
    descriptors_from_learning_loop_services,
)
from app.services.teaching_interaction_runtime import (
    TeachingInteractionRuntimeService,
)


def test_learning_readiness_reports_versions_and_fails_closed_without_evidence(
    app,
    client,
) -> None:
    app.state.runtime_agent_readiness = SimpleNamespace(
        capability_descriptors=(
            SimpleNamespace(
                domain="learning_loop",
                capability_id="TEACHING_INTERACTION_V1",
                runtime_id="teaching_interaction",
                version="teaching-interaction-v1",
                agent_version="learning-agent-v1",
                enabled=True,
                supported_actions=("request_more_hint",),
                supports_pause=False,
                supports_resume=False,
                supports_approval=True,
                supports_input=False,
                control_scope="learning_loop",
                result_contract="learning_action_response.v1",
            ),
        ),
        release_registry=RuntimeCanaryReleaseRegistry(),
    )

    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    capability = response.json()["capabilities"][0]
    assert capability["agent_version"] == "learning-agent-v1"
    assert capability["runtime_plan_version"] == "teaching-interaction-v1"
    assert capability["structural_release_eligible"] is False
    assert capability["semantic_release_eligible"] is False
    assert capability["canary_release_eligible"] is False
    assert capability["canary_reason"] == "canary_release_evidence_missing"


def test_learning_readiness_reports_next_gate_after_structural_evidence(
    app,
    client,
) -> None:
    class StructuralEvidenceRegistry(RuntimeCanaryReleaseRegistry):
        def structural_eligible(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return True

        def release_eligible(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return True

        def reason(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return "canary_release_evidence_approved"

    app.state.runtime_agent_readiness = SimpleNamespace(
        capability_descriptors=(
            SimpleNamespace(
                domain="learning_loop",
                capability_id="TEACHING_INTERACTION_V1",
                runtime_id="teaching_interaction",
                version="teaching-interaction-v1",
                agent_version="learning-agent-v1",
                enabled=True,
                supported_actions=("request_more_hint",),
                supports_pause=True,
                supports_resume=True,
                supports_approval=True,
                supports_input=True,
                control_scope="learning_loop",
                result_contract="learning_action_response.v1",
            ),
        ),
        release_registry=StructuralEvidenceRegistry(),
    )

    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    capability = response.json()["capabilities"][0]
    assert capability["structural_release_eligible"] is True
    assert capability["semantic_release_eligible"] is True
    assert capability["canary_release_eligible"] is False
    assert capability["canary_reason"] == "release_authorization_missing"
    assert capability["blockers"] == ["release_authorization_missing"]


def test_learning_readiness_uses_shared_release_registry_and_never_executes(
    app,
    client,
) -> None:
    class SpyRegistry(RuntimeCanaryReleaseRegistry):
        def release_eligible(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.called = True
            return super().release_eligible(*args, **kwargs)

        def reason(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.reason_called = True
            return super().reason(*args, **kwargs)

    registry = SpyRegistry()
    app.state.runtime_agent_readiness = SimpleNamespace(
        capability_descriptors=(
            SimpleNamespace(
                domain="learning_loop",
                capability_id="LEARNING_PROGRESS_V1",
                runtime_id="learning_progress",
                version="learning-progress-v1",
                agent_version="learning-agent-v1",
                enabled=False,
                supported_actions=("start_retest",),
                supports_pause=False,
                supports_resume=False,
                supports_approval=True,
                supports_input=False,
                control_scope="learning_loop",
                result_contract="learning_action_response.v1",
            ),
        ),
        release_registry=registry,
    )

    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    capability = response.json()["capabilities"][0]
    assert capability["canary_release_eligible"] is False
    assert capability["canary_reason"] == "canary_release_evidence_missing"
    assert registry.called is True
    assert registry.reason_called is True


def test_learning_readiness_does_not_infer_missing_agent_version_from_artifact(
    app,
    client,
) -> None:
    registry = RuntimeCanaryReleaseRegistry()
    app.state.runtime_agent_readiness = SimpleNamespace(
        capability_descriptors=(
            SimpleNamespace(
                domain="learning_loop",
                capability_id="TEACHING_INTERACTION_V1",
                runtime_id="teaching_interaction",
                version="teaching-interaction-v1",
                enabled=True,
                supported_actions=("request_more_hint",),
                supports_pause=False,
                supports_resume=False,
                supports_approval=True,
                supports_input=False,
                control_scope="learning_loop",
                result_contract="learning_action_response.v1",
            ),
        ),
        release_registry=registry,
    )

    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    capability = response.json()["capabilities"][0]
    assert capability["agent_version"] == ""
    assert capability["runtime_plan_version"] == "teaching-interaction-v1"
    assert capability["canary_release_eligible"] is False
    assert capability["canary_reason"] == (
        "canary_artifact_version_expectation_missing"
    )


def test_real_learning_descriptors_bind_identity_but_missing_evidence_stays_closed(
    app,
    client,
) -> None:
    descriptors = descriptors_from_learning_loop_services(
        teaching_interaction=TeachingInteractionRuntimeService(
            cast(Any, object()), enabled=True
        ),
        learning_progress=LearningProgressRuntimeService(
            cast(Any, object()), enabled=True
        ),
    )
    app.state.runtime_agent_readiness = SimpleNamespace(
        capability_descriptors=descriptors,
        release_registry=RuntimeCanaryReleaseRegistry(),
    )

    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    capabilities = response.json()["capabilities"]
    assert [item["agent_version"] for item in capabilities] == [
        "learning-agent-v1",
        "learning-agent-v1",
    ]
    assert all(item["canary_release_eligible"] is False for item in capabilities)
    assert all(
        item["canary_reason"] == "canary_release_evidence_missing"
        for item in capabilities
    )
