from __future__ import annotations

from types import SimpleNamespace


def test_learning_runtime_readiness_projects_only_learning_descriptors(
    client,
) -> None:
    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["version"] == "v1"
    assert payload["provider_called"] is False

    capabilities = payload["capabilities"]
    assert [item["capability_id"] for item in capabilities] == [
        "TEACHING_INTERACTION_V1",
        "LEARNING_PROGRESS_V1",
    ]
    required = {
        "capability_id",
        "domain",
        "runtime_id",
        "version",
        "enabled",
        "supported_actions",
        "supports_pause",
        "supports_resume",
        "supports_approval",
        "supports_input",
        "control_scope",
        "result_contract",
        "blockers",
    }
    assert all(required <= set(item) for item in capabilities)
    assert all(item["domain"] == "learning_loop" for item in capabilities)
    assert all(item["supports_pause"] is False for item in capabilities)
    assert all(item["supports_resume"] is False for item in capabilities)
    assert all(item["supports_approval"] is True for item in capabilities)
    assert all(item["supports_input"] is False for item in capabilities)
    assert "learning_runtime_authorized_paired_evidence_missing" in payload[
        "blockers"
    ]
    assert "learning_runtime_pause_not_implemented" in payload["blockers"]
    assert "learning_runtime_resume_not_implemented" in payload["blockers"]
    assert "learning_runtime_input_not_implemented" in payload["blockers"]


class _ForbiddenExecutionDescriptor:
    domain = "learning_loop"
    capability_id = "TEACHING_INTERACTION_V1"
    runtime_id = "teaching_interaction"
    version = "teaching-interaction-v1"
    enabled = True
    supported_actions = ("request_more_hint",)
    supports_pause = False
    supports_resume = False
    supports_approval = True
    supports_input = False
    control_scope = "learning_loop"
    result_contract = "learning_action_response.v1"

    def supports(self, *_args, **_kwargs):
        raise AssertionError("readiness must not call supports")

    def build_plan(self, *_args, **_kwargs):
        raise AssertionError("readiness must not call build_plan")

    def execute(self, *_args, **_kwargs):
        raise AssertionError("readiness must not call execute")


def test_learning_runtime_readiness_is_provider_free_and_domain_filtered(
    app,
    client,
) -> None:
    app.state.runtime_agent_readiness = SimpleNamespace(
        capability_descriptors=(
            {
                "domain": "task_agent",
                "capability_id": "TASK_ONLY",
            },
            _ForbiddenExecutionDescriptor(),
        )
    )

    response = client.get("/api/v1/learning/runtime-readiness")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider_called"] is False
    assert [item["capability_id"] for item in payload["capabilities"]] == [
        "TEACHING_INTERACTION_V1"
    ]
    assert "LEARNING_PROGRESS_V1" not in {
        item["capability_id"] for item in payload["capabilities"]
    }
    assert "learning_runtime_descriptor_missing" in payload["blockers"]
