from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.dependencies import get_db, require_admin
from app.models import AgentRunModel, AgentRunNodeModel, TaskModel
from app.repositories import AgentRunRepository
from app.runtime import AgentRun, build_runtime_observability
from app.services.learning_loop import LearningLoopService
from app.services.task_query_service import TaskQueryService

router = APIRouter(
    prefix="/debug/execution",
    tags=["execution-debug"],
    dependencies=[Depends(require_admin)],
)
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


def _redact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], _redact(value))


def _order_runtime_nodes(
    nodes: list[AgentRunNodeModel], restored_runtime: AgentRun | None
) -> list[AgentRunNodeModel]:
    """Return the debug projection in the immutable plan's node order.

    Database row order is deliberately not execution order. The restored
    Runtime plan is the durable source of truth for the operator-facing graph;
    unknown legacy rows remain visible after all declared nodes in a stable
    lexical order.
    """

    if restored_runtime is None:
        return sorted(nodes, key=lambda node: node.node_id)
    positions = {
        node.node_id: index
        for index, node in enumerate(restored_runtime.plan.nodes)
    }
    return sorted(
        nodes,
        key=lambda node: (positions.get(node.node_id, len(positions)), node.node_id),
    )


def _read_runtime_handoff(run: AgentRunModel | None) -> dict[str, Any]:
    """Read the persisted Runtime ownership envelope without trusting its shape."""

    if run is None or not isinstance(run.control_data, dict):
        return {}
    handoff = run.control_data.get("runtime_handoff")
    return dict(handoff) if isinstance(handoff, dict) else {}


async def _read_learning_runtime_projection(
    request: Request,
    db: AsyncSession,
    task: TaskModel,
) -> dict[str, Any]:
    """Expose the latest LearningLoop checkpoint without private payloads."""

    run = await db.scalar(
        select(AgentRunModel)
        .where(
            AgentRunModel.task_id == task.id,
            AgentRunModel.run_kind.in_(
                ("teaching_interaction", "learning_progress")
            ),
        )
        .order_by(AgentRunModel.created_at.desc())
        .limit(1)
    )
    if run is None:
        return {}
    service = getattr(request.app.state, "learning_loop", None)
    if not isinstance(service, LearningLoopService):
        return {}
    try:
        status = await service.runtime_status(db, run.id, user_id=task.user_id)
    except NotFoundError:
        # A stale or partially-created learning run must not break the main
        # execution debug projection. The dedicated status endpoint remains
        # the authoritative error surface for that run.
        return {}
    return {
        "run_id": status.run_id,
        "runtime_id": status.runtime_id,
        "run_kind": status.run_kind,
        "status": status.status,
        "state_version": status.state_version,
        "control_scope": status.control_scope,
        "available_controls": list(status.available_controls),
        "approval_required": status.approval_required,
        "resumable": status.resumable,
        "node_statuses": [
            node.model_dump(mode="json") for node in status.node_statuses
        ],
    }


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
        "teaching_path": {},
        "verification": {},
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
        result_metrics = result.get("metrics", {})
        result_metrics = (
            result_metrics if isinstance(result_metrics, dict) else {}
        )
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
            "teaching_mode": str(result_metrics.get("teaching_mode", "")),
            "teaching_execution_path": str(
                result_metrics.get("teaching_execution_path", "")
            ),
            "student_verification_executed": bool(
                result_metrics.get("student_verification_executed", False)
            ),
            "verification_method": str(
                result_metrics.get("verification_method", "not_run")
            ),
            "manual_review_required": bool(
                result_metrics.get("manual_review_required", False)
            ),
            "first_confirmed_error_found": bool(
                result_metrics.get("first_confirmed_error_found", False)
            ),
            "hint_level": str(result_metrics.get("hint_level", "")),
            "hint_request_count": int(
                result_metrics.get("hint_request_count", 0)
            ),
            "solution_packet_reused": bool(
                result_metrics.get("solution_packet_reused", False)
            ),
            "full_solution_disclosed": bool(
                result_metrics.get("full_solution_disclosed", False)
            ),
            "additional_model_calls": int(
                result_metrics.get("additional_model_calls", 0)
            ),
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
            ("teaching_path", record["teaching_execution_path"] or "none"),
            ("verification", record["verification_method"]),
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
    return _redact_dict(
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
        .where(
            AgentRunModel.task_id == task_id,
            AgentRunModel.run_kind == "runtime",
        )
        .order_by(AgentRunModel.created_at.desc())
        .limit(1)
    )
    if run is None:
        run = await db.scalar(
            select(AgentRunModel)
            .where(AgentRunModel.task_id == task_id)
            .order_by(AgentRunModel.created_at.desc())
            .limit(1)
        )
    runtime_handoff = _read_runtime_handoff(run)
    learning_runtime = await _read_learning_runtime_projection(request, db, task)
    runtime_nodes = []
    runtime_children = []
    runtime_checkpoints = []
    restored_runtime: AgentRun | None = None
    runtime_launch_decision: dict[str, Any] = {}
    runtime_compatibility_snapshot: dict[str, Any] = {}
    runtime_goal_contract: dict[str, Any] = {}
    runtime_observability: dict[str, Any] = {
        "schema_version": "1",
        "observations": [],
        "decisions": [],
        "verifications": [],
        "nodes": [],
    }
    if run is not None and run.run_kind == "runtime":
        restored_runtime = await AgentRunRepository(db).restore(run.id)
        if restored_runtime is not None:
            runtime_observability = build_runtime_observability(restored_runtime)
        if (
            restored_runtime is not None
            and restored_runtime.launch_decision is not None
        ):
            runtime_launch_decision = (
                restored_runtime.launch_decision.model_dump(mode="json")
            )
        if (
            restored_runtime is not None
            and restored_runtime.compatibility_snapshot is not None
        ):
            runtime_compatibility_snapshot = (
                restored_runtime.compatibility_snapshot.model_dump(mode="json")
            )
        if restored_runtime is not None and restored_runtime.goal_contract is not None:
            runtime_goal_contract = restored_runtime.goal_contract.model_dump(
                mode="json"
            )
        runtime_nodes = _order_runtime_nodes(
            list(
            (
                await db.scalars(
                    select(AgentRunNodeModel)
                    .where(AgentRunNodeModel.run_id == run.id)
                    .order_by(AgentRunNodeModel.node_id)
                )
            ).all()
            ),
            restored_runtime,
        )
        runtime_children = list(
            (
                await db.scalars(
                    select(AgentRunModel)
                    .where(AgentRunModel.parent_run_id == run.id)
                    .order_by(AgentRunModel.created_at)
                )
            ).all()
        )
        runtime_checkpoints = await AgentRunRepository(db).list_checkpoints(run.id)
    runtime_metrics = (
        run.metrics_data
        if run is not None and isinstance(run.metrics_data, dict)
        else {}
    )
    result_metrics = result.get("metrics", {})
    result_metrics = result_metrics if isinstance(result_metrics, dict) else {}
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
        {
            "key": "teaching_planning",
            "label": "教学规划",
            "duration_ms": result_metrics.get("teaching_planning_ms", 0),
        },
        {
            "key": "student_verification",
            "label": "学生过程核对",
            "duration_ms": result_metrics.get("student_verification_ms", 0),
        },
        {
            "key": "hint",
            "label": "分级提示",
            "duration_ms": result_metrics.get("hint_generation_ms", 0),
        },
        {
            "key": "disclosure",
            "label": "答案披露过滤",
            "duration_ms": result_metrics.get("disclosure_filter_ms", 0),
        },
    ]
    return _redact_dict(
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
            "learning_runtime": learning_runtime,
            "runtime": {
                "run_kind": run.run_kind if run is not None else "",
                "run_id": run.id if run is not None else "",
                "plan_id": run.plan_id if run is not None else "",
                "plan_version": run.plan_version if run is not None else "",
                "iteration": run.iteration if run is not None else 0,
                "status": run.status if run is not None else "",
                "goal": (
                    restored_runtime.goal
                    if restored_runtime is not None
                    else ""
                ),
                "goal_contract": runtime_goal_contract,
                "state_version": run.state_version if run is not None else 0,
                "launch_decision": runtime_launch_decision,
                "compatibility_snapshot": runtime_compatibility_snapshot,
                "observability": runtime_observability,
                "handoff": runtime_handoff,
                "budget": (
                    run.budget_data
                    if run is not None and isinstance(run.budget_data, dict)
                    else {}
                ),
                "terminal_reason": (
                    run.terminal_reason if run is not None else ""
                ),
                "children": [
                    {
                        "run_id": child.id,
                        "run_kind": child.run_kind,
                        "parent_node_id": child.parent_node_id,
                        "agent_id": child.agent_id,
                        "status": child.status,
                        "state_version": child.state_version,
                        "plan_id": child.plan_id,
                    }
                    for child in runtime_children
                ],
                "checkpoints": [
                    {
                        "sequence": checkpoint.sequence,
                        "state_version": checkpoint.state_version,
                        "status": checkpoint.status,
                        "event_sequence": checkpoint.event_sequence,
                        "created_at": checkpoint.created_at.isoformat(),
                    }
                    for checkpoint in runtime_checkpoints
                ],
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "node_type": node.node_type,
                        "handler_id": node.handler_id,
                        "target_id": node.target_id,
                        "execution_key": node.execution_key,
                        "runtime_effect": (
                            node.observation_data.get("_runtime_effect", {})
                            if isinstance(node.observation_data, dict)
                            else {}
                        ),
                        "effect_status": node.effect_status,
                        "status": node.status,
                        "attempt": node.attempt,
                        "error_code": node.error_code,
                        "observation": node.observation_data,
                    }
                    for node in runtime_nodes
                ],
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
                "teaching": {
                    key: result_metrics.get(key)
                    for key in (
                        "teaching_mode",
                        "teaching_execution_path",
                        "student_attempt_present",
                        "solution_packet_reused",
                        "student_verification_executed",
                        "verification_method",
                        "manual_review_required",
                        "first_confirmed_error_found",
                        "hint_level",
                        "hint_source",
                        "hint_request_count",
                        "next_check_generated",
                        "answer_disclosure_mode",
                        "full_solution_disclosed",
                        "teaching_state_restored",
                        "additional_model_calls",
                        "teaching_planning_ms",
                        "student_verification_ms",
                        "hint_generation_ms",
                        "disclosure_filter_ms",
                    )
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
