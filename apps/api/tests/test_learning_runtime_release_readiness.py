from __future__ import annotations

from types import SimpleNamespace

from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry


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
    assert capability["canary_release_eligible"] is False
    assert capability["canary_reason"] == "canary_release_evidence_missing"


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
