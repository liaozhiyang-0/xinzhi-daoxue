from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.contracts import (
    AgentRequest,
    Intent,
    RouteDecision,
    RouteStatus,
    Scene,
    TaskRequestContext,
)
from app.services.agent_runtime import AgentExecutionPlanner, AgentInputMapper

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentDryRunRequest(BaseModel):
    question: str = Field(default="示例问题", max_length=4000)
    course_id: str = Field(default="CT", max_length=16)
    intent: Intent = Intent.EXPLAIN_CONCEPT
    retrieved_context: str = Field(
        default="[dry-run retrieval context]", max_length=12000
    )
    options: dict[str, Any] = Field(default_factory=dict)


def _lifecycle_status(definition: Any, configured: bool, mock_ready: bool) -> str:
    if definition.publication_status == "published" and definition.enabled:
        return "published"
    if configured:
        return "cloud_configured"
    if mock_ready:
        return "mock_ready"
    if definition.publication_status == "planned":
        return "planned"
    return "disabled"


@router.get("", summary="列出非敏感 Agent 运行状态")
@router.get("/status", summary="列出非敏感 Agent 运行状态")
async def list_agent_status(request: Request) -> dict[str, Any]:
    registry = request.app.state.agent_registry
    settings = request.app.state.settings
    agents = []
    mock_provider = request.app.state.development_mock_provider
    for definition in registry.list_agents():
        configured = registry.is_configured(definition.agent_id, settings)
        mock_ready = bool(
            definition.development.mock_enabled
            and mock_provider.profile_exists(definition.development.mock_profile)
        )
        agents.append(
            {
                "agent_id": definition.agent_id,
                "display_name": definition.display_name,
                "version": definition.version,
                "scene": definition.scene,
                "provider": definition.provider,
                "enabled": definition.enabled,
                "publication_status": definition.publication_status,
                "mode": definition.mode,
                "course_ids": sorted(definition.course_ids),
                "supports": sorted(definition.supports),
                "fallback_agent_id": definition.fallback_agent_id,
                "configured": configured,
                "flow_configured": bool(
                    registry.resolve_flow_id(definition.agent_id, settings)
                ),
                "runtime_available": registry.is_runtime_available(
                    definition.agent_id, settings
                ),
                "parser_type": definition.provider_config.parser_type,
                "retrieval_policy": definition.retrieval_policy.policy_name,
                "retrieval_mode": definition.retrieval_policy.mode,
                "fallback_type": definition.fallback.type,
                "fallback_handler": definition.fallback.handler,
                "mock_ready": mock_ready,
                "mock_available": mock_provider.is_allowed(definition.agent_id),
                "mock_profile": definition.development.mock_profile,
                "lifecycle_status": _lifecycle_status(
                    definition, configured, mock_ready
                ),
                "recent_contract_test": request.app.state.agent_contract_results.get(
                    definition.agent_id, {"status": "not_run"}
                ),
                "runtime_readiness": request.app.state.runtime_agent_readiness.inspect(
                    definition.agent_id
                ).to_dict(),
            }
        )
    provider_status = getattr(request.app.state.provider, "runtime_status", None)
    return {
        "agents": agents,
        "provider_runtime": provider_status() if provider_status else {},
        "mock_actions_enabled": bool(
            settings.app_env != "production" and settings.allow_agent_mocks
        ),
        "debug_actions_enabled": bool(
            settings.app_env != "production" and settings.rag_debug_enabled
        ),
    }


@router.get(
    "/runtime-readiness",
    summary="查看每个 Agent 的 Runtime 迁移就绪度与阻塞原因",
)
async def list_runtime_readiness(request: Request) -> dict[str, Any]:
    readiness = request.app.state.runtime_agent_readiness
    items = readiness.as_dicts()
    counts: dict[str, int] = {}
    for item in items:
        status = str(item["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "provider_called": False,
        "release_gate_required": readiness.launch_policy.release_gate_required,
        "counts": counts,
        "agents": items,
    }


@router.get("/{agent_id}", summary="查看单个 Agent 的脱敏定义")
async def show_agent(agent_id: str, request: Request) -> dict[str, Any]:
    registry = request.app.state.agent_registry
    try:
        definition = registry.get(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent 未注册") from exc
    payload = {
        "agent_id": definition.agent_id,
        "display_name": definition.display_name,
        "version": definition.version,
        "schema_version": definition.schema_version,
        "enabled": definition.enabled,
        "publication_status": definition.publication_status,
        "provider": definition.provider,
        "flow_env_key": definition.flow_env,
        "flow_configured": registry.is_configured(agent_id, request.app.state.settings),
        "capabilities": {
            "user_roles": sorted(definition.capabilities.user_roles),
            "courses": sorted(definition.capabilities.courses),
            "intents": sorted(definition.capabilities.intents),
            "input_modes": sorted(definition.capabilities.input_modes),
        },
        "required_inputs": sorted(definition.input_contract.required),
        "optional_inputs": sorted(definition.input_contract.optional),
        "parser_type": definition.provider_config.parser_type,
        "retrieval_policy": asdict(definition.retrieval_policy),
        "fallback": asdict(definition.fallback),
        "development": asdict(definition.development),
        "input_mapping": [asdict(item) for item in definition.input_rules],
        "output_mapping": [asdict(item) for item in definition.output_rules],
        "mock_ready": bool(
            definition.development.mock_enabled
            and request.app.state.development_mock_provider.profile_exists(
                definition.development.mock_profile
            )
        ),
        "deprecation_warnings": (
            ["legacy_registry_fields"]
            if not definition.input_contract.required
            and definition.provider == "xingchen"
            else []
        ),
    }
    return payload


@router.post("/{agent_id}/dry-run", summary="预览映射和执行计划，不调用云端")
async def dry_run_agent(
    agent_id: str, payload: AgentDryRunRequest, request: Request
) -> dict[str, Any]:
    registry = request.app.state.agent_registry
    try:
        definition = registry.get(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent 未注册") from exc
    input_mode = "text"
    agent_request = AgentRequest(
        session_id="dry_run_session",
        user_id="dry_run_user",
        scene=Scene(definition.scene),
        course_id=payload.course_id.upper(),
        intent=payload.intent,
        canonical_input={"text": payload.question},
        options={
            **payload.options,
            "question": payload.question,
            "retrieved_context": payload.retrieved_context,
            "request_id": "dry_run_request",
        },
    )
    decision = RouteDecision(
        agent_id=agent_id,
        scene=definition.scene,
        course_id=payload.course_id.upper(),
        intent=payload.intent.value,
        route_status=RouteStatus.SELECTED,
        reason="debug dry-run",
        retrieval_required=definition.retrieval_policy.enabled,
        provider_required=definition.provider == "xingchen",
    )
    plan = AgentExecutionPlanner(registry, request.app.state.settings).build(
        decision, agent_request
    )
    mapped = AgentInputMapper().map(
        definition,
        TaskRequestContext.from_agent_request(
            agent_request,
            input_mode=input_mode,
        ),
        retrieval_context=payload.retrieved_context,
    )
    return {
        "dry_run": True,
        "cloud_called": False,
        "agent_id": agent_id,
        "configured": plan.configured,
        "capabilities": {
            "courses": sorted(definition.capabilities.courses),
            "intents": sorted(definition.capabilities.intents),
            "input_modes": sorted(definition.capabilities.input_modes),
        },
        "required_inputs": sorted(definition.input_contract.required),
        "mapping_preview": mapped.redacted_preview,
        "field_lengths": mapped.field_lengths,
        "execution_plan": plan.model_dump(mode="json"),
        "parser_type": definition.provider_config.parser_type,
        "fallback_handler": definition.fallback.handler,
    }
