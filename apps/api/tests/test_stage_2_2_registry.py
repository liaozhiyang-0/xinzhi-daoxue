import json

import httpx
import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AttachmentRef
from app.core.config import Settings
from app.core.errors import (
    AgentConfigurationIncompleteError,
    AgentInputNotSupportedError,
    RouteInvalidTargetError,
)
from app.providers.xingchen import XingchenCloudProvider


def test_registry_resolves_flow_and_unconfigured_agent_stays_unavailable() -> None:
    registry = AgentRegistry()
    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_api_key="key",
        xingchen_api_secret="secret",
        xingchen_solver_ct_flow_id="solver-flow",
        _env_file=None,
    )

    assert registry.resolve_flow_id("SOLVER_CT_V1", settings) == "solver-flow"
    assert registry.is_runtime_available("SOLVER_CT_V1", settings) is True
    assert registry.is_runtime_available("LEARN_01_KNOWLEDGE_QA_V1", settings) is False


def test_answer_check_routes_directly_to_solver_without_dead_intermediate() -> None:
    decision = TaskRouter(AgentRegistry(), Settings(_env_file=None)).route(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent="check_user_solution",
            canonical_input={"text": "我的答案是 2A"},
        )
    )

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.fallback_used is False
    assert decision.original_agent_id is None


def test_cloud_router_rejects_unknown_and_self_targets() -> None:
    router = TaskRouter(AgentRegistry(), Settings(_env_file=None))
    request = AgentRequest(
        session_id="session",
        user_id="user",
        course_id="CT",
        intent="general_qa",
        canonical_input={"text": "问题"},
    )
    with pytest.raises(RouteInvalidTargetError):
        router.route_cloud_response(json.dumps({"target_agent_id": "UNKNOWN"}), request)
    with pytest.raises(RouteInvalidTargetError):
        router.route_cloud_response(
            json.dumps({"target_agent_id": "ROUTER_01_FALLBACK_V1"}), request
        )


async def test_provider_reports_missing_enabled_agent_configuration() -> None:
    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_api_key="key",
        xingchen_api_secret="secret",
        _env_file=None,
    )
    with pytest.raises(AgentConfigurationIncompleteError):
        await XingchenCloudProvider(settings).run(
            "SOLVER_CT_V1",
            AgentRequest(
                session_id="session",
                user_id="user",
                canonical_input={"text": "问题"},
            ),
        )


async def test_text_image_contract_rejects_pdf_without_silent_drop() -> None:
    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_api_key="key",
        xingchen_api_secret="secret",
        xingchen_solver_ct_flow_id="flow",
        _env_file=None,
    )
    request = AgentRequest(
        session_id="session",
        user_id="user",
        canonical_input={"text": "问题"},
        attachments=[
            AttachmentRef(
                file_id="file",
                filename="problem.pdf",
                content_type="application/pdf",
                size_bytes=1,
                storage_key="local:problem.pdf",
            )
        ],
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500))
    )
    with pytest.raises(AgentInputNotSupportedError):
        await XingchenCloudProvider(settings, client=client).run(
            "SOLVER_CT_V1", request
        )
    await client.aclose()


def test_agent_status_api_contains_no_flow_values(client) -> None:
    response = client.get("/api/v1/agents/status")
    assert response.status_code == 200
    payload = response.json()
    solver = next(
        item for item in payload["agents"] if item["agent_id"] == "SOLVER_CT_V1"
    )
    assert "flow_configured" in solver
    assert "flow_id" not in solver
