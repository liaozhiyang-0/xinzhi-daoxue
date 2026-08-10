from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.agents.internal import InternalAgentHub
from app.contracts import ImageInput, ModelResponse, ModelUsage
from app.core.config import Settings
from app.services.model_registry import ModelRegistry
from app.services.model_service import ModelService


class FakeModelService:
    def __init__(self) -> None:
        self.registry = ModelRegistry(Settings(_env_file=None))
        self.providers = {
            "iflytek_spark": SimpleNamespace(configured=True),
            "dashscope": SimpleNamespace(configured=True),
        }
        self.calls: list[dict[str, Any]] = []

    async def generate_json_for_task(
        self, task_type: str, **kwargs: Any
    ) -> ModelResponse:
        self.calls.append({"task_type": task_type, **kwargs})
        schema_name = getattr(kwargs.get("schema"), "__name__", "")
        payload = (
            {
                "method": "mesh analysis",
                "steps": ["define currents", "build equations"],
                "equations_to_build": ["KVL"],
                "assumptions": [],
                "missing_information": [],
                "needs_tool_verification": True,
                "risk_level": "medium",
            }
            if schema_name == "CircuitPlan"
            else {
                "target_agent_id": "RESEARCH_01_ACADEMIC_SEARCH_V1",
                "intent": "general_qa",
                "course_id": "UNKNOWN",
                "confidence": 0.94,
                "reason": "the request asks for recent papers",
                "reason_codes": ["paper_search"],
                "task_subtype": "academic_search",
            }
            if schema_name == "OverallRouteDecision"
            else {
                "course": "CT",
                "confidence": 0.9,
                "reason_codes": ["capacitor"],
            }
        )
        content = json.dumps(payload, ensure_ascii=False)
        return ModelResponse(
            provider="dashscope",
            model="qwen3.5-flash",
            content=content,
            usage=ModelUsage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
            elapsed_ms=12,
        )

    async def generate_for_task(self, task_type: str, **kwargs: Any) -> ModelResponse:
        self.calls.append({"task_type": task_type, **kwargs})
        return ModelResponse(
            provider="iflytek_spark",
            model="spark-x",
            content="Use mesh analysis and verify equations with a symbolic tool.",
            usage=ModelUsage(prompt_tokens=12, completion_tokens=18, total_tokens=30),
            elapsed_ms=20,
        )

    async def analyze_images_for_task(
        self, task_type: str, **kwargs: Any
    ) -> ModelResponse:
        self.calls.append({"task_type": task_type, **kwargs})
        content = json.dumps(
            {
                "recognized_text": ["2Ω"],
                "diagram_description": "single-loop circuit",
                "components": [
                    {
                        "component_type": "resistor",
                        "value": "2Ω",
                        "connections": ["loop"],
                    }
                ],
                "uncertain_info": [],
                "confidence": 0.9,
            },
            ensure_ascii=False,
        )
        return ModelResponse(
            provider="dashscope",
            model="qwen3.7-plus",
            content=content,
            usage=ModelUsage(prompt_tokens=20, completion_tokens=30, total_tokens=50),
            elapsed_ms=25,
        )


def hub() -> tuple[InternalAgentHub, FakeModelService]:
    service = FakeModelService()
    return InternalAgentHub(cast(ModelService, service)), service


def test_internal_agent_catalog_maps_to_model_routes() -> None:
    agent_hub, _ = hub()

    agents = agent_hub.list_agents()

    # The catalog is extensible; do not freeze the count as local agents grow.
    assert len(agents) >= 12
    assert {item["agent_id"] for item in agents} >= {
        "COURSE_CLASSIFIER_LOCAL_V1",
        "CIRCUIT_PLANNER_LOCAL_V1",
        "CIRCUIT_VISION_EXTRACTOR_LOCAL_V1",
        "RESEARCH_INTENT_CLASSIFIER_LOCAL_V1",
        "RESEARCH_FRONTIER_BRIEF_LOCAL_V1",
        "RESEARCH_FRONTIER_KNOWLEDGE_LOCAL_V1",
    }
    assert all(item["configured"] for item in agents)


@pytest.mark.asyncio
async def test_overall_router_uses_compact_structured_contract() -> None:
    agent_hub, service = hub()

    result = await agent_hub.run_text(
        "OVERALL_ROUTER_LOCAL_V1",
        input_text="查找最新的电子信息领域相关论文",
        max_tokens=160,
    )

    assert result.structured_result["target_agent_id"] == (
        "RESEARCH_01_ACADEMIC_SEARCH_V1"
    )
    assert service.calls[0]["task_type"] == "overall_routing"
    assert service.calls[0]["extra_options"] == {"max_tokens": 160}


@pytest.mark.asyncio
async def test_course_classifier_uses_model_service_and_schema() -> None:
    agent_hub, service = hub()

    result = await agent_hub.run_text(
        "COURSE_CLASSIFIER_LOCAL_V1",
        input_text="为什么电容电压不能突变？",
        max_tokens=96,
    )

    assert result.structured_result["course"] == "CT"
    assert result.total_tokens == 48
    assert [call["task_type"] for call in service.calls] == [
        "course_classification",
        "structured_output_normalization",
    ]
    assert service.calls[0]["extra_options"] == {"max_tokens": 96}
    system_prompt = service.calls[1]["messages"][0]["content"]
    assert "JSON Schema" in system_prompt
    assert '"course"' in system_prompt


@pytest.mark.asyncio
async def test_circuit_agent_uses_reason_then_structure_pipeline() -> None:
    agent_hub, service = hub()

    result = await agent_hub.run_text(
        "CIRCUIT_PLANNER_LOCAL_V1",
        input_text="plan a two-mesh circuit",
        max_tokens=128,
    )

    assert result.structured_result["needs_tool_verification"] is True
    assert result.provider == "iflytek_spark+dashscope"
    assert result.model == "spark-x->qwen3.5-flash"
    assert result.total_tokens == 48
    assert [call["task_type"] for call in service.calls] == [
        "complex_circuit_reasoning",
        "structured_output_normalization",
    ]


@pytest.mark.asyncio
async def test_runtime_structured_fallback_option_reaches_spark_pipeline() -> None:
    agent_hub, service = hub()

    await agent_hub.run_text(
        "CIRCUIT_PLANNER_LOCAL_V1",
        input_text="plan a two-mesh circuit",
        max_tokens=128,
        extra_options={"_allow_structured_fallback": True},
    )

    assert service.calls[0]["extra_options"] == {
        "_allow_structured_fallback": True,
        "max_tokens": 128,
    }
    assert service.calls[1]["extra_options"] == {
        "_allow_structured_fallback": True,
        "max_tokens": 128,
    }


@pytest.mark.asyncio
async def test_circuit_vision_agent_uses_schema_and_image_route() -> None:
    agent_hub, service = hub()

    result = await agent_hub.run_vision(
        "CIRCUIT_VISION_EXTRACTOR_LOCAL_V1",
        prompt="extract components",
        images=[ImageInput(source_type="url", value="https://example.com/a.png")],
        max_tokens=128,
        high_resolution=False,
    )

    assert result.structured_result["recognized_text"] == ["2Ω"]
    assert result.model == "qwen3.7-plus"
    assert "JSON Schema" in service.calls[0]["prompt"]
    assert service.calls[0]["high_resolution"] is False


def test_internal_agents_api_lists_subordinate_policy(client: Any) -> None:
    response = client.get("/api/v1/internal-agents")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["agents"]) >= 12
    assert payload["execution_policy"].startswith("subordinate_only")
