import httpx
from app.contracts import AgentRequest, KnowledgeCourseId, KnowledgeHit
from app.core.config import Settings
from app.providers.xingchen import (
    XingchenCloudProvider,
    build_workflow_payload,
    parse_json_answer,
    parse_sse_answer,
)
from app.services.task_runner import TaskRunner


def request() -> AgentRequest:
    return AgentRequest(
        session_id="session-test",
        user_id="user-test",
        canonical_input={"question": "求电阻电压"},
    )


def test_xingchen_request_payload_mapping() -> None:
    settings = Settings(
        app_env="test",
        xingchen_solver_ct_flow_id="test-flow",
        xingchen_uid="local-demo-user",
    )
    payload = build_workflow_payload(settings, request())
    assert payload == {
        "flow_id": "test-flow",
        "uid": "local-demo-user",
        "parameters": {"AGENT_USER_INPUT": "求电阻电压"},
        "ext": {"caller": "workflow"},
        "stream": False,
    }


def test_xingchen_json_response_parsing() -> None:
    payload = {
        "code": 0,
        "choices": [{"delta": {"content": "最终回答"}, "finish_reason": "stop"}],
    }
    assert parse_json_answer(payload) == "最终回答"


def test_xingchen_sse_response_minimal_parsing() -> None:
    body = (
        'data: {"code":0,"choices":[{"delta":{"content":"第一段"}}]}\n\n'
        'data: {"code":0,"choices":[{"delta":{"content":"第二段"}}]}\n\n'
        "data: [DONE]\n\n"
    )
    assert parse_sse_answer(body) == "第一段第二段"


def test_xingchen_context_is_limited_and_keeps_sources() -> None:
    hits = [
        KnowledgeHit(
            course_id=KnowledgeCourseId.CIRCUIT_THEORY,
            course_name="电路理论",
            document_path=f"chapter-{index}.md",
            title=f"chapter {index}",
            content="方法参考" * 600,
            score=1.0,
            source_ref=f"kb://CT/chapter-{index}",
        )
        for index in range(1, 5)
    ]
    augmented = TaskRunner._with_xingchen_context(request(), hits)
    text = augmented.canonical_input["question"]
    assert isinstance(text, str)
    assert len(text) <= 3000
    assert augmented.options["xingchen_knowledge_sources"] == [
        "kb://CT/chapter-1",
        "kb://CT/chapter-2",
        "kb://CT/chapter-3",
    ]


async def test_xingchen_provider_returns_answer_and_artifact() -> None:
    captured: dict[str, object] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        captured["authorization"] = http_request.headers["Authorization"]
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "code": 0,
                "choices": [
                    {"delta": {"content": "Provider 回答"}, "finish_reason": "stop"}
                ],
            },
        )

    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_api_key="test-key",
        xingchen_api_secret="test-secret",
        xingchen_solver_ct_flow_id="test-flow",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await XingchenCloudProvider(settings, client=client).run(
        "SOLVER_CT_V1", request(), stream=False
    )
    await client.aclose()
    assert result.provider == "xingchen"
    assert result.answer == "Provider 回答"
    assert result.artifacts[0].content["answer"] == "Provider 回答"
    assert captured["authorization"] == "Bearer test-key:test-secret"
