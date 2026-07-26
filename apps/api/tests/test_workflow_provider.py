import httpx
import pytest
from app.agents import AgentRegistry
from app.core.config import Settings
from app.providers.workflow import XingchenWorkflowProvider


@pytest.mark.asyncio
async def test_xingchen_workflow_provider_standardizes_registered_flow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key:test-secret"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "delta": {
                            "content": '{"answer_text":"标准化回答","confidence":0.8}'
                        }
                    }
                ]
            },
        )

    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_api_key="test-key",
        xingchen_api_secret="test-secret",
        xingchen_solver_ct_flow_id="test-flow",
        _env_file=None,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = XingchenWorkflowProvider(settings, AgentRegistry(), client=client)

    result = await provider.invoke_workflow("test-flow", {"AGENT_USER_INPUT": "问题"})

    assert result.answer_text == "标准化回答"
    assert result.structured_result["confidence"] == 0.8
    await client.aclose()
