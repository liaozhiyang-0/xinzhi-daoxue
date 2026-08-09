from __future__ import annotations


def test_runtime_readiness_exposes_cross_entry_capabilities_provider_free(
    client,
) -> None:
    response = client.get("/api/v1/agents/runtime-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_called"] is False
    capabilities = payload["capabilities"]
    assert isinstance(capabilities, list)
    assert any(item["domain"] == "task_agent" for item in capabilities)
    assert any(item["domain"] == "learning_loop" for item in capabilities)
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
        "result_contract",
        "control_scope",
    }
    assert all(required <= set(item) for item in capabilities)
    assert all(
        not any(
            secret in str(item).casefold()
            for secret in ("token", "password", "secret")
        )
        for item in capabilities
    )

    agents = payload["agents"]
    general = next(item for item in agents if item["agent_id"] == "GENERAL_QUESTION_V1")
    assert general["runtime_capabilities"]
    assert all(
        item["domain"] == "task_agent"
        for item in general["runtime_capabilities"]
    )
