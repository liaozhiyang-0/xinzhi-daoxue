from __future__ import annotations

from time import perf_counter

import pytest
from app.agents import AgentRegistry
from app.contracts import AgentRequest, Intent, Scene
from app.core.config import Settings
from app.main import create_app
from app.providers.development_mock import MOCK_WARNING, DevelopmentMockProvider
from app.services.academic_writing_runtime import AcademicWritingRuntimeService
from fastapi.testclient import TestClient

ACTIVE_WORKFLOW_AGENTS = (
    "ROUTER_01_FALLBACK_V1",
    "TEACH_01_LESSON_PREP_V1",
    "TEACH_02_ASSIGNMENT_REVIEW_V1",
    "RESEARCH_02_ACADEMIC_WRITING_V1",
    "RESEARCH_03_DATA_ANALYSIS_V1",
)


def mock_request(agent_id: str, registry: AgentRegistry) -> AgentRequest:
    definition = registry.get(agent_id)
    return AgentRequest(
        session_id="mock-session",
        user_id="mock-user",
        scene=Scene(definition.scene),
        course_id="CT",
        intent=Intent.EXPLAIN_CONCEPT,
        canonical_input={"text": "开发态正常输入"},
        options={"allow_agent_mock": True, "request_id": "mock-request"},
    )


@pytest.mark.parametrize("agent_id", ACTIVE_WORKFLOW_AGENTS)
async def test_each_active_workflow_runs_definition_driven_mock(
    settings: Settings, agent_id: str
) -> None:
    runtime_settings = settings.model_copy(update={"allow_agent_mocks": True})
    registry = AgentRegistry()
    provider = DevelopmentMockProvider(runtime_settings, registry)
    started = perf_counter()

    result = await provider.run(agent_id, mock_request(agent_id, registry))

    assert (perf_counter() - started) * 1000 < 100
    assert result.provider == "mock"
    assert result.mock_used is True
    assert result.mock_profile
    assert result.cloud_status == "not_called"
    assert result.business_data
    assert MOCK_WARNING in result.warnings


async def test_lesson_prep_mock_matches_runtime_business_contract(
    settings: Settings,
) -> None:
    runtime_settings = settings.model_copy(update={"allow_agent_mocks": True})
    registry = AgentRegistry()
    provider = DevelopmentMockProvider(runtime_settings, registry)

    result = await provider.run(
        "TEACH_01_LESSON_PREP_V1",
        mock_request("TEACH_01_LESSON_PREP_V1", registry),
    )

    assert "formative_assessment" in result.business_data
    assert result.business_data["formative_assessment"] == []
    assert "assessment" not in result.business_data


async def test_academic_writing_mock_matches_runtime_business_contract(
    settings: Settings,
) -> None:
    runtime_settings = settings.model_copy(update={"allow_agent_mocks": True})
    registry = AgentRegistry()
    provider = DevelopmentMockProvider(runtime_settings, registry)

    result = await provider.run(
        "RESEARCH_02_ACADEMIC_WRITING_V1",
        mock_request("RESEARCH_02_ACADEMIC_WRITING_V1", registry),
    )

    assert result.business_data["revised_text"]
    assert result.business_data["revision_notes"]
    assert result.business_data["citation_check"] == "需要人工核验引用与事实"
    assert result.business_data["unsupported_claims"] == []
    assert AcademicWritingRuntimeService._verification_state(result) == "approval"


async def test_production_forces_mock_off(settings: Settings) -> None:
    production = settings.model_copy(
        update={"app_env": "production", "allow_agent_mocks": True}
    )
    registry = AgentRegistry()

    result = await DevelopmentMockProvider(production, registry).run(
        ACTIVE_WORKFLOW_AGENTS[0], mock_request(ACTIVE_WORKFLOW_AGENTS[0], registry)
    )

    assert result.provider == "none"
    assert result.mock_used is False
    assert result.structured_result["status"] == "planned"
    assert result.cloud_status == "not_called"


def test_agent_debug_api_is_redacted_and_runs_contracts(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"allow_agent_mocks": True}))
    with TestClient(app) as client:
        listing = client.get("/api/v1/agents")
        assert listing.status_code == 200
        serialized = listing.text.casefold()
        assert "authorization" not in serialized
        assert "api_secret" not in serialized
        assert 'flow_id":' not in serialized

        mock = client.post(
            "/api/v1/debug/agents/TEACH_01_LESSON_PREP_V1/mock",
            json={
                "question": "准备节点电压法课程",
                "course_id": "CT",
                "allow_mock": True,
            },
        )
        assert mock.status_code == 200
        assert mock.json()["mock_used"] is True
        assert mock.json()["remote_provider_called"] is False

        contracts = client.post(
            "/api/v1/debug/agents/TEACH_01_LESSON_PREP_V1/contract-tests"
        )
        assert contracts.status_code == 200
        assert contracts.json()["total"] == 3
        assert contracts.json()["passed"] == 3


def test_production_debug_actions_are_disabled(settings: Settings) -> None:
    app = create_app(
        settings.model_copy(update={"app_env": "production", "allow_agent_mocks": True})
    )
    with TestClient(app) as client:
        listing = client.get("/api/v1/agents").json()
        assert listing["mock_actions_enabled"] is False
        response = client.post(
            "/api/v1/debug/agents/TEACH_01_LESSON_PREP_V1/mock",
            json={"question": "不会执行", "allow_mock": True},
        )
        assert response.status_code == 403


def test_all_active_workflow_fixture_sets_pass(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"allow_agent_mocks": True}))
    with TestClient(app) as client:
        for agent_id in ACTIVE_WORKFLOW_AGENTS:
            response = client.post(f"/api/v1/debug/agents/{agent_id}/contract-tests")
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["total"] == 3
            assert payload["passed"] == 3, payload
