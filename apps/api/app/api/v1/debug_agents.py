from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.contracts import AgentRequest, Intent, Scene
from app.core.config import PROJECT_ROOT
from app.core.errors import ValidationAppError

router = APIRouter(prefix="/debug/agents", tags=["agent-debug"])
FIXTURE_PATH = (
    PROJECT_ROOT
    / "apps"
    / "api"
    / "tests"
    / "fixtures"
    / "agents"
    / "workflow_contract_cases.json"
)


class AgentDebugRequest(BaseModel):
    question: str = Field(default="开发态契约测试输入", max_length=4000)
    course_id: str = Field(default="CT", max_length=16)
    intent: Intent = Intent.EXPLAIN_CONCEPT
    canonical_input: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    allow_mock: bool = False


class AgentCompareRequest(AgentDebugRequest):
    allow_cloud: bool = False
    cloud_sample: dict[str, Any] | None = None


def _ensure_debug(request: Request, *, action: bool = True) -> None:
    settings = request.app.state.settings
    if not settings.rag_debug_enabled:
        raise HTTPException(status_code=404, detail="Agent Debug未启用")
    if action and settings.app_env == "production":
        raise HTTPException(status_code=403, detail="生产环境禁止Agent Debug执行动作")


def _agent_request(
    agent_id: str, payload: AgentDebugRequest, request: Request
) -> AgentRequest:
    definition = request.app.state.agent_registry.get(agent_id)
    canonical_input = {"text": payload.question, **payload.canonical_input}
    return AgentRequest(
        session_id="debug_agent_session",
        user_id="debug_agent_user",
        scene=Scene(definition.scene),
        course_id=payload.course_id.upper(),
        intent=payload.intent,
        canonical_input=canonical_input,
        options={
            **payload.options,
            "request_id": "debug_agent_request",
            "allow_agent_mock": payload.allow_mock,
        },
    )


def _result_payload(result: Any, *, elapsed_ms: int) -> dict[str, Any]:
    return {
        "status": result.structured_result.get("status", result.status.value),
        "agent_id": result.agent_id,
        "provider": result.provider,
        "answer_text": result.answer,
        "business_data": result.business_data,
        "confidence": result.confidence,
        "warnings": result.warnings,
        "mock_used": result.mock_used,
        "mock_profile": result.mock_profile,
        "cloud_called": result.cloud_status not in {"", "not_run", "not_called"},
        "cloud_status": result.cloud_status,
        "local_latency_ms": elapsed_ms,
        "provider_latency_ms": result.metrics.provider_latency_ms,
        "validation_errors": [],
    }


@router.post("/{agent_id}/validate")
async def validate_agent(agent_id: str, request: Request) -> dict[str, Any]:
    _ensure_debug(request)
    try:
        definition = request.app.state.agent_registry.get(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent未注册") from exc
    mock_provider = request.app.state.development_mock_provider
    errors = []
    if definition.development.mock_enabled and not mock_provider.profile_exists(
        definition.development.mock_profile
    ):
        errors.append("mock_profile_not_found")
    result = {
        "agent_id": agent_id,
        "valid": not errors,
        "validation_errors": errors,
        "required_inputs": sorted(definition.input_contract.required),
        "mapped_sources": sorted(item.source for item in definition.input_rules),
        "parser_type": definition.provider_config.parser_type,
        "retrieval_policy": definition.retrieval_policy.policy_name,
        "fallback_handler": definition.fallback.handler,
        "mock_ready": definition.development.mock_enabled and not errors,
        "flow_configured": request.app.state.agent_registry.is_configured(
            agent_id, request.app.state.settings
        ),
    }
    request.app.state.agent_contract_results[agent_id] = {
        "status": "passed" if result["valid"] else "failed",
        "source": "validate",
    }
    return result


@router.post("/{agent_id}/mock")
async def run_mock(
    agent_id: str, payload: AgentDebugRequest, request: Request
) -> dict[str, Any]:
    _ensure_debug(request)
    started = perf_counter()
    try:
        result = await request.app.state.development_mock_provider.run(
            agent_id, _agent_request(agent_id, payload, request)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent未注册") from exc
    except ValidationAppError as exc:
        return {
            "status": "validation_error",
            "agent_id": agent_id,
            "provider": "none",
            "mock_used": False,
            "cloud_called": False,
            "warnings": [],
            "validation_errors": [exc.message],
            "details": exc.details,
            "local_latency_ms": int((perf_counter() - started) * 1000),
        }
    return _result_payload(result, elapsed_ms=int((perf_counter() - started) * 1000))


def _schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _schema(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return (
            ["empty"] if not value else [sorted({_type_name(item) for item in value})]
        )
    return _type_name(value)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


@router.post("/{agent_id}/compare")
async def compare_mock_cloud(
    agent_id: str, payload: AgentCompareRequest, request: Request
) -> dict[str, Any]:
    _ensure_debug(request)
    mock_request = payload.model_copy(update={"allow_mock": True})
    mock_result = await run_mock(agent_id, mock_request, request)
    cloud_payload: dict[str, Any] | None = payload.cloud_sample
    cloud_called = False
    definition = request.app.state.agent_registry.get(agent_id)
    if payload.allow_cloud:
        if not (
            definition.enabled
            and definition.publication_status == "published"
            and request.app.state.agent_registry.is_runtime_available(
                agent_id, request.app.state.settings
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="仅已发布且配置完整的Agent允许真实Cloud结构比较",
            )
        result = await request.app.state.provider.run(
            agent_id, _agent_request(agent_id, payload, request), stream=False
        )
        cloud_payload = _result_payload(result, elapsed_ms=0)
        cloud_called = True
    if cloud_payload is None:
        raise HTTPException(
            status_code=422,
            detail="需要提供脱敏cloud_sample或显式允许已发布Agent调用Cloud",
        )
    mock_business = mock_result.get("business_data", {})
    cloud_business = cloud_payload.get("business_data", {})
    mock_fields = set(mock_business) if isinstance(mock_business, dict) else set()
    cloud_fields = set(cloud_business) if isinstance(cloud_business, dict) else set()
    return {
        "agent_id": agent_id,
        "cloud_called": cloud_called,
        "mock_used": bool(mock_result.get("mock_used")),
        "mock_schema": _schema(mock_result),
        "cloud_schema": _schema(cloud_payload),
        "business_data": {
            "missing_in_cloud": sorted(mock_fields - cloud_fields),
            "extra_in_cloud": sorted(cloud_fields - mock_fields),
            "mock_types": _schema(mock_business),
            "cloud_types": _schema(cloud_business),
        },
        "semantic_quality_compared": False,
    }


@router.post("/{agent_id}/contract-tests")
async def run_contract_tests(agent_id: str, request: Request) -> dict[str, Any]:
    _ensure_debug(request)
    request.app.state.agent_registry.get(agent_id)
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    selected = [item for item in cases if item.get("agent_id") == agent_id]
    results = []
    for case in selected:
        raw_input = case.get("input", {})
        payload = AgentDebugRequest(
            question=str(raw_input.get("question", "")),
            course_id=str(raw_input.get("course_id", "CT")),
            canonical_input=dict(raw_input.get("canonical_input", {})),
            options=dict(raw_input.get("options", {})),
            allow_mock=True,
        )
        output = await run_mock(agent_id, payload, request)
        required_fields = set(case.get("required_business_fields", []))
        actual_fields = set(output.get("business_data", {}))
        expected = str(case.get("expected_status", "success"))
        passed = (
            output.get("status") == expected
            and required_fields <= actual_fields
            and all(
                forbidden not in json.dumps(output, ensure_ascii=False)
                for forbidden in case.get("forbidden_strings", [])
            )
        )
        results.append({"case_id": case.get("case_id"), "passed": passed})
    summary = {
        "agent_id": agent_id,
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "results": results,
        "manual_review_required": True,
    }
    request.app.state.agent_contract_results[agent_id] = {
        "status": "passed" if summary["passed"] == summary["total"] else "failed",
        "source": "fixtures",
        "passed": summary["passed"],
        "total": summary["total"],
    }
    return summary
