from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.task_query_service import TaskQueryService

router = APIRouter(prefix="/debug/execution", tags=["execution-debug"])
SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "secret",
    "token",
    "flow_id",
    "uid",
    "raw_prompt",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.casefold() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


@router.get("/{task_id}", response_model=dict[str, Any])
async def get_execution(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not request.app.state.settings.rag_debug_enabled:
        raise HTTPException(status_code=404, detail="Execution Debug 未启用")
    service = TaskQueryService(db)
    task = await service.get(task_id)
    events = await service.list_events(task_id)
    result = task.result_content or {}
    structured = result.get("structured_result", {})
    structured = structured if isinstance(structured, dict) else {}
    knowledge = structured.get("knowledge", {})
    knowledge = knowledge if isinstance(knowledge, dict) else {}
    context = structured.get("workflow_context") or {}
    summary = structured.get("execution_summary") or {}
    presentation = structured.get("presentation") or {}
    evidence_view = structured.get("evidence_view") or []
    validation = structured.get("citation_validation") or {"status": "not_run"}
    result_validation = structured.get("validation") or {"status": "not_run"}
    input_content = task.input_content if isinstance(task.input_content, dict) else {}
    input_options = input_content.get("options", {})
    input_options = input_options if isinstance(input_options, dict) else {}
    route = input_options.get("_routing", {})
    route = route if isinstance(route, dict) else {}
    materials = structured.get("material_extraction") or input_options.get(
        "_material_extraction", {}
    )
    try:
        definition = request.app.state.agent_registry.get(task.agent_id)
        mapping = [
            {
                "parameter": rule.parameter_name,
                "source": rule.source,
                "transform": rule.transform,
                "max_length": rule.max_length,
            }
            for rule in definition.input_rules
        ]
    except KeyError:
        mapping = []
    timings = summary.get("timings", result.get("timings", {}))
    timings = timings if isinstance(timings, dict) else {}
    waterfall = [
        {"key": "route", "label": "路由", "duration_ms": timings.get("route_ms", 0)},
        {
            "key": "retrieval",
            "label": "检索",
            "duration_ms": timings.get("retrieval_ms", 0),
        },
        {
            "key": "context",
            "label": "上下文",
            "duration_ms": timings.get("context_ms", 0),
        },
        {"key": "cloud", "label": "云端", "duration_ms": timings.get("cloud_ms", 0)},
        {
            "key": "citation",
            "label": "引用",
            "duration_ms": timings.get("citation_ms", 0),
        },
        {
            "key": "validation",
            "label": "结果校验",
            "duration_ms": timings.get("validation_ms", 0),
        },
    ]
    return _redact(
        {
            "task": {
                "id": task.id,
                "status": task.status.value,
                "course_id": task.course_id,
                "intent": task.intent,
                "agent_id": task.agent_id,
                "provider": task.provider,
                "request_id": context.get("request_id", ""),
                "created_at": task.created_at.isoformat(),
                "completed_at": (
                    task.completed_at.isoformat() if task.completed_at else None
                ),
            },
            "overview": presentation,
            "request": {
                "raw_input": input_content.get("canonical_input", {}),
                "materials": materials,
            },
            "route": route or summary.get("route", {}),
            "execution_plan": structured.get("execution_plan", {}),
            "retrieval": {
                "policy": summary.get("retrieval_policy", ""),
                "rag_mode": summary.get("rag_mode", "no_rag"),
                "status": result.get("rag_status", "disabled"),
                "evidence_status": result.get("evidence_status", "insufficient"),
                "candidate_trace": knowledge.get("trace", {}),
                "final_evidence": evidence_view,
                "workflow_evidence_ids": context.get("workflow_evidence_ids", []),
                "used_evidence_ids": context.get("used_evidence_ids", []),
            },
            "workflow": {
                "provider": result.get("provider", task.provider),
                "cloud_status": result.get("cloud_status", "not_run"),
                "request_id": result.get("request_id", ""),
                "response_status": structured.get("status", result.get("status", "")),
                "parser_status": structured.get("parse_status", "not_reported"),
                "mock": bool(
                    result.get("mock_used") or result.get("provider") == "mock"
                ),
                "input_mapping": mapping,
                "output": {
                    "status": structured.get("status", ""),
                    "business_data": structured.get("business_data", {}),
                    "parse_status": structured.get("parse_status", "not_reported"),
                },
            },
            "citation": validation,
            "validation": result_validation,
            "reroute": {
                "reroute_count": route.get("reroute_count", 0),
                "visited_agents": route.get("visited_agents", []),
                "automatic": route.get("route_source") == "automatic_reroute",
            },
            "final": {
                "answer": result.get("answer", ""),
                "citations": result.get("citations", []),
                "fallback_used": result.get("fallback_used", False),
                "fallback_reason": result.get("fallback_reason", ""),
                "warnings": result.get("warnings", []),
            },
            "performance": {
                "waterfall": waterfall,
                "total_ms": timings.get("total_ms", 0),
            },
            "events": [
                {
                    "sequence": event.sequence,
                    "type": event.event_type,
                    "data": event.event_data,
                    "created_at": event.created_at.isoformat(),
                }
                for event in events
            ],
        }
    )
