from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models import AgentRunModel, TaskModel
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


@router.get("/metrics/summary", response_model=dict[str, Any])
async def get_metrics_summary(
    request: Request,
    course_id: str | None = Query(default=None, max_length=32),
    intent: str | None = Query(default=None, max_length=64),
    agent_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not request.app.state.settings.rag_debug_enabled:
        raise HTTPException(status_code=404, detail="Execution Debug 未启用")
    statement = (
        select(TaskModel, AgentRunModel)
        .join(AgentRunModel, AgentRunModel.task_id == TaskModel.id)
        .order_by(AgentRunModel.created_at.desc())
        .limit(limit)
    )
    if course_id:
        statement = statement.where(TaskModel.course_id == course_id)
    if intent:
        statement = statement.where(TaskModel.intent == intent)
    if agent_id:
        statement = statement.where(AgentRunModel.agent_id == agent_id)
    rows = list((await db.execute(statement)).all())
    records: list[dict[str, Any]] = []
    aggregates: dict[str, dict[str, dict[str, int]]] = {
        "agent": {},
        "course": {},
        "intent": {},
        "status": {},
    }
    distributions: dict[str, dict[str, int]] = {
        "route": {},
        "quality": {},
        "citation_failure": {},
    }
    retrieval_attempts = 0
    retrieval_successes = 0
    for task, run in rows:
        result = task.result_content if isinstance(task.result_content, dict) else {}
        structured = result.get("structured_result", {})
        structured = structured if isinstance(structured, dict) else {}
        presentation = structured.get("presentation", {})
        presentation = presentation if isinstance(presentation, dict) else {}
        metrics = run.metrics_data if isinstance(run.metrics_data, dict) else {}
        input_options = task.input_content.get("options", {})
        input_options = input_options if isinstance(input_options, dict) else {}
        route = input_options.get("_routing", {})
        route = route if isinstance(route, dict) else {}
        quality = structured.get("quality_gate", {})
        quality = quality if isinstance(quality, dict) else {}
        citation = structured.get("citation_validation", {})
        citation = citation if isinstance(citation, dict) else {}
        evidence_status = str(result.get("evidence_status", "not_run"))
        record = {
            "task_id": task.id,
            "trace_id": run.trace_id or "",
            "agent_id": run.agent_id,
            "course_id": task.course_id,
            "intent": task.intent,
            "status": run.status,
            "start_time": run.started_at.isoformat() if run.started_at else None,
            "end_time": run.completed_at.isoformat() if run.completed_at else None,
            "latency_ms": run.latency_ms,
            "model_provider": run.provider,
            "model_name": str(metrics.get("model_name", "")),
            "model_calls": run.model_calls,
            "tool_calls": run.tool_calls,
            "retrieval_calls": run.retrieval_calls,
            "input_tokens": metrics.get("input_tokens"),
            "output_tokens": metrics.get("output_tokens"),
            "fallback_used": bool(result.get("fallback_used")),
            "error_type": task.failure_category,
            "sanitized_summary": str(presentation.get("title", task.intent))[:160],
            "route_source": str(route.get("route_source", "unknown")),
            "retrieval_status": evidence_status,
            "quality_status": str(quality.get("status", "not_checked")),
            "citation_status": str(citation.get("status", "not_run")),
            "context_estimated_tokens": metrics.get("context_estimated_tokens", 0),
            "context_budget_tokens": metrics.get("context_budget_tokens", 0),
            "context_cache_hit": bool(metrics.get("context_cache_hit", False)),
            "memory_retrieval_count": metrics.get("memory_retrieval_count", 0),
        }
        records.append(record)
        for dimension, value in (
            ("agent", run.agent_id),
            ("course", task.course_id),
            ("intent", task.intent),
            ("status", run.status),
        ):
            bucket = aggregates[dimension].setdefault(
                value, {"runs": 0, "latency_ms": 0, "fallbacks": 0}
            )
            bucket["runs"] += 1
            bucket["latency_ms"] += int(run.latency_ms or 0)
            bucket["fallbacks"] += int(bool(result.get("fallback_used")))
        for name, value in (
            ("route", record["route_source"]),
            ("quality", record["quality_status"]),
        ):
            key = str(value)
            distributions[name][key] = distributions[name].get(key, 0) + 1
        citation_status = str(record["citation_status"])
        if citation_status not in {"passed", "not_run", "not_applicable"}:
            distributions["citation_failure"][citation_status] = (
                distributions["citation_failure"].get(citation_status, 0) + 1
            )
        if run.retrieval_calls:
            retrieval_attempts += 1
            retrieval_successes += int(evidence_status in {"sufficient", "partial"})
    slowest = sorted(
        records, key=lambda item: int(item.get("latency_ms") or 0), reverse=True
    )[:10]
    return _redact(
        {
            "count": len(records),
            "aggregates": aggregates,
            "distributions": distributions,
            "provider_call_count": sum(item.model_calls for _, item in rows),
            "input_tokens": sum(int(item.get("input_tokens") or 0) for item in records),
            "output_tokens": sum(
                int(item.get("output_tokens") or 0) for item in records
            ),
            "fallback_count": sum(int(item["fallback_used"]) for item in records),
            "retrieval_success_rate": (
                retrieval_successes / retrieval_attempts if retrieval_attempts else None
            ),
            "slowest_runs": slowest,
            "records": records,
        }
    )


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
    run = await db.scalar(
        select(AgentRunModel)
        .where(AgentRunModel.task_id == task_id)
        .order_by(AgentRunModel.created_at.desc())
        .limit(1)
    )
    runtime_metrics = (
        run.metrics_data
        if run is not None and isinstance(run.metrics_data, dict)
        else {}
    )
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
            "duration_ms": runtime_metrics.get(
                "context_build_latency_ms", timings.get("context_ms", 0)
            ),
        },
        {
            "key": "compaction",
            "label": "会话压缩",
            "duration_ms": runtime_metrics.get("compaction_latency_ms", 0),
        },
        {
            "key": "memory",
            "label": "记忆治理",
            "duration_ms": runtime_metrics.get("memory_latency_ms", 0),
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
                "context": {
                    "message_count": runtime_metrics.get("message_count", 0),
                    "recent_message_count": runtime_metrics.get(
                        "recent_message_count", 0
                    ),
                    "older_message_count": runtime_metrics.get(
                        "older_message_count", 0
                    ),
                    "summary_version": runtime_metrics.get("summary_version", 0),
                    "estimated_tokens": runtime_metrics.get(
                        "context_estimated_tokens", 0
                    ),
                    "budget_tokens": runtime_metrics.get(
                        "context_budget_tokens", 0
                    ),
                    "trimmed": runtime_metrics.get("context_trimmed", False),
                    "cache_hit": runtime_metrics.get("context_cache_hit", False),
                    "cache_backend": runtime_metrics.get(
                        "context_cache_backend", "none"
                    ),
                    "memory_retrieval_count": runtime_metrics.get(
                        "memory_retrieval_count", 0
                    ),
                    "memory_write_count": runtime_metrics.get(
                        "memory_write_count", 0
                    ),
                },
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
