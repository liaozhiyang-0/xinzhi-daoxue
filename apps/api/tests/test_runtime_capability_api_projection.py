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
        "status",
        "structural_release_eligible",
        "semantic_release_eligible",
        "canary_release_eligible",
        "canary_reason",
        "blockers",
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
    general = next(
        item for item in agents if item["agent_id"] == "GENERAL_QUESTION_V1"
    )
    assert general["runtime_capabilities"]
    assert all(
        item["agent_version"] == "1.0"
        for item in general["runtime_capabilities"]
    )
    assert all(
        item["domain"] == "task_agent"
        for item in general["runtime_capabilities"]
    )

    research = next(
        item
        for item in capabilities
        if item["capability_id"] == "RESEARCH_03_DATA_ANALYSIS_V1"
    )
    assert research["version"] == "research-v2"
    research_agent = next(
        item
        for item in agents
        if item["agent_id"] == "RESEARCH_03_DATA_ANALYSIS_V1"
    )
    research_descriptor = research_agent["runtime_capabilities"][0]
    assert research_descriptor["version"] == "research-v2"
    assert research_agent["runtime_plan_available"] == research_descriptor["enabled"]

    agents_by_id = {item["agent_id"]: item for item in agents}
    for capability in capabilities:
        if capability["domain"] == "task_agent":
            agent = agents_by_id[capability["capability_id"]]
            assert capability["status"] == agent["status"]
            assert (
                capability["canary_release_eligible"]
                == agent["canary_release_eligible"]
            )
            assert (
                capability["structural_release_eligible"]
                == agent["structural_release_eligible"]
            )
            assert (
                capability["semantic_release_eligible"]
                == agent["semantic_release_eligible"]
            )
            assert capability["canary_reason"] == agent["canary_reason"]
            assert capability["blockers"] == agent["blockers"]

    learning = next(
        item for item in capabilities if item["domain"] == "learning_loop"
    )
    assert learning["canary_release_eligible"] is False
    if learning["enabled"]:
        assert learning["status"] == "runtime_implemented"
        assert learning["canary_reason"] == "canary_release_evidence_missing"
        assert learning["blockers"] == ["canary_release_evidence_missing"]
    else:
        assert learning["status"] == "blocked"
        assert learning["canary_reason"] == "runtime_capability_disabled"
        assert learning["blockers"] == ["runtime_capability_disabled"]
