from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.contracts import AgentRequest, AttachmentRef
from app.core.config import Settings
from app.providers.xingchen import XingchenCloudProvider


def response() -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={
            "code": 0,
            "choices": [
                {"delta": {"content": "星辰回答"}, "finish_reason": "stop"}
            ],
        },
    )


@pytest.mark.asyncio
async def test_provider_selects_flow_id_from_agent() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return response()

    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_base_url="https://xingchen.example",
        xingchen_api_key="test-key",
        xingchen_api_secret="test-secret",
        xingchen_solver_ct_flow_id="solver-flow",
        xingchen_knowledge_qa_flow_id="knowledge-flow",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = XingchenCloudProvider(settings, client=client)
    request = AgentRequest(
        session_id="session",
        user_id="user",
        course_id="AE",
        intent="explain_concept",
        canonical_input={"text": "什么是负反馈"},
    )

    result = await provider.run("LEARN_01_KNOWLEDGE_QA_V1", request)
    await client.aclose()

    assert captured[0]["flow_id"] == "knowledge-flow"
    assert captured[0]["parameters"] == {"AGENT_USER_INPUT": "什么是负反馈"}
    assert result.agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
    assert result.answer == "星辰回答"


@pytest.mark.asyncio
async def test_provider_preserves_single_image_mapping(tmp_path: Path) -> None:
    image_path = tmp_path / "storage" / "image" / "circuit.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-png")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/upload_file"):
            captured["upload_body"] = request.content
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"url": "https://files.example/circuit.png"},
                },
            )
        captured["workflow"] = json.loads(request.content)
        return response()

    settings = Settings(
        app_env="test",
        xingchen_enabled=True,
        xingchen_base_url="https://xingchen.example",
        xingchen_api_key="test-key",
        xingchen_api_secret="test-secret",
        xingchen_solver_ct_flow_id="solver-flow",
        local_storage_path=tmp_path / "storage",
    )
    request = AgentRequest(
        session_id="session",
        user_id="user",
        canonical_input={"text": "请解答图片题"},
        attachments=[
            AttachmentRef(
                file_id="file",
                filename="circuit.png",
                content_type="image/png",
                size_bytes=8,
                storage_key="local:image/circuit.png",
            )
        ],
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await XingchenCloudProvider(settings, client=client).run(
        "SOLVER_CT_V1", request
    )
    await client.aclose()

    assert b"fake-png" in captured["upload_body"]
    workflow = captured["workflow"]
    assert isinstance(workflow, dict)
    assert workflow["flow_id"] == "solver-flow"
    assert workflow["parameters"]["USER_INPUT_image"] == (
        "https://files.example/circuit.png"
    )
    assert result.structured_result["input_type"] == "image"
