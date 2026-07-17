import json

import httpx
import pytest
from app.contracts import (
    AgentRequest,
    AttachmentRef,
    KnowledgeCourseId,
    KnowledgeHit,
)
from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.providers.xingchen import (
    XingchenCloudProvider,
    build_workflow_payload,
    get_single_image,
    parse_json_answer,
    parse_sse_answer,
    standardize_answer,
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


def test_xingchen_structured_answer_mapping_is_best_effort() -> None:
    answer = json.dumps(
        {
            "answer_text": "完整分步骤解答",
            "problem_summary": "求等效电阻",
            "key_equations": ["R=U/I"],
            "final_answer": "R=5 Ω",
            "assumptions": ["采用关联参考方向"],
            "remaining_risks": ["图片参数需复核"],
            "confidence": 0.8,
        },
        ensure_ascii=False,
    )

    structured = standardize_answer(answer, input_type="text")

    assert structured == {
        "status": "completed",
        "input_type": "text",
        "answer_text": "完整分步骤解答",
        "problem_summary": "求等效电阻",
        "key_equations": ["R=U/I"],
        "final_answer": "R=5 Ω",
        "assumptions": ["采用关联参考方向"],
        "remaining_risks": ["图片参数需复核"],
        "confidence": 0.8,
    }


def test_xingchen_unstructured_answer_is_preserved() -> None:
    structured = standardize_answer("不是 JSON，但必须保留", input_type="image")

    assert structured["answer_text"] == "不是 JSON，但必须保留"
    assert structured["input_type"] == "image"
    assert structured["confidence"] is None


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
    context = text.split("【本地知识库方法参考】\n", 1)[1].split(
        "\n【使用约束】", 1
    )[0]
    assert len(context) <= 2000
    assert "本地知识库仅用于方法参考。" in text
    assert "题目参数、电路连接和参考方向以用户输入为准。" in text
    assert "不得使用知识库内容覆盖题目事实。" in text
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
    assert result.structured_result["answer_text"] == "Provider 回答"
    assert result.structured_result["confidence"] is None
    assert result.artifacts[0].content["answer_text"] == "Provider 回答"
    assert captured["authorization"] == "Bearer test-key:test-secret"


async def test_xingchen_uploads_single_image_and_injects_url(tmp_path) -> None:
    image_path = tmp_path / "storage" / "image" / "circuit.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-png")
    image_request = AgentRequest(
        session_id="session-image",
        user_id="user-image",
        canonical_input={"text": "请解答图片中的电路题"},
        attachments=[
            AttachmentRef(
                file_id="file-image",
                filename="circuit.png",
                content_type="image/png",
                size_bytes=8,
                storage_key="local:image/circuit.png",
                checksum_sha256="test-checksum",
            )
        ],
    )
    captured: dict[str, object] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url.path.endswith("/upload_file"):
            captured["upload_content_type"] = http_request.headers["Content-Type"]
            captured["upload_body"] = http_request.content
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "message": "success",
                    "data": {"url": "https://files.example/circuit.png"},
                },
            )
        captured["workflow_payload"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "code": 0,
                "choices": [
                    {"delta": {"content": "图片解题结果"}, "finish_reason": "stop"}
                ],
            },
        )

    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_api_key="test-key",
        xingchen_api_secret="test-secret",
        xingchen_solver_ct_flow_id="test-flow",
        local_storage_path=tmp_path / "storage",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await XingchenCloudProvider(settings, client=client).run(
        "SOLVER_CT_V1", image_request, stream=False
    )
    await client.aclose()

    assert str(captured["upload_content_type"]).startswith("multipart/form-data")
    assert b"fake-png" in captured["upload_body"]
    payload = captured["workflow_payload"]
    assert isinstance(payload, dict)
    assert payload["parameters"]["USER_INPUT_image"] == (
        "https://files.example/circuit.png"
    )
    assert result.structured_result["input_type"] == "image"
    assert result.answer == "图片解题结果"


def test_xingchen_rejects_multiple_images() -> None:
    attachment = AttachmentRef(
        file_id="file-image",
        filename="circuit.png",
        content_type="image/png",
        size_bytes=8,
        storage_key="local:image/circuit.png",
    )
    image_request = AgentRequest(
        session_id="session-image",
        user_id="user-image",
        canonical_input={},
        attachments=[attachment, attachment.model_copy(update={"file_id": "file-2"})],
    )
    with pytest.raises(ValidationAppError, match="单张图片"):
        get_single_image(image_request)
