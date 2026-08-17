from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import TaskModel, TaskStatus
from app.observability.model_tracer import ModelTracer
from app.observability.tracer import TraceStore
from app.services.task_observability import elapsed_ms, percentile_ms
from app.services.task_queue import TaskQueue

_RECENT_TASK_LIMIT = 200


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def model_snapshot(tracer: ModelTracer) -> dict[str, Any]:
    records = tracer.list()
    total = len(records)
    completed = sum(1 for item in records if item.status == "completed")
    failed = total - completed
    fallback = sum(1 for item in records if item.fallback_used)
    latency_ms = [item.elapsed_ms for item in records if item.elapsed_ms is not None]
    prompt_tokens = sum(
        item.prompt_tokens or 0 for item in records if item.prompt_tokens is not None
    )
    completion_tokens = sum(
        item.completion_tokens or 0
        for item in records
        if item.completion_tokens is not None
    )
    total_tokens = sum(
        item.total_tokens or 0 for item in records if item.total_tokens is not None
    )
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "fallback": fallback,
        "latency_ms_sum": sum(latency_ms),
        "latency_ms_p95": percentile_ms(latency_ms, 0.95) or 0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "by_provider": _count_by(records, lambda item: item.provider),
        "by_model": _count_by(records, lambda item: item.model),
        "by_task_type": _count_by(records, lambda item: item.task_type),
        "by_status": {"completed": completed, "failed": failed},
    }


def trace_snapshot(store: TraceStore) -> dict[str, Any]:
    records = store.list()
    return {
        "total": len(records),
        "by_route_status": _count_by(
            records, lambda item: str(item.get("route_status", "unknown"))
        ),
        "by_selected_agent": _count_by(
            records, lambda item: str(item.get("selected_agent", "unknown"))
        ),
        "by_course": _count_by(
            records, lambda item: str(item.get("course", "unknown"))
        ),
        "node_total": sum(len(item.get("nodes", [])) for item in records),
    }


async def task_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    async with session_factory() as db:
        status_rows = (
            await db.execute(
                select(TaskModel.status, func.count(TaskModel.id)).group_by(
                    TaskModel.status
                )
            )
        ).all()
        status_counts: dict[str, int] = {}
        for status, count in status_rows:
            value = status.value if hasattr(status, "value") else status
            status_counts[str(value)] = _safe_int(count)

        recent_rows = list(
            (
                await db.execute(
                    select(TaskModel).order_by(TaskModel.created_at.desc()).limit(
                        _RECENT_TASK_LIMIT
                    )
                )
            ).scalars()
        )

    latencies = [
        elapsed_ms(task.started_at, task.completed_at)
        for task in recent_rows
        if task.started_at is not None and task.completed_at is not None
    ]
    queue_latencies = [
        elapsed_ms(task.created_at, task.started_at)
        for task in recent_rows
        if task.started_at is not None
    ]
    return {
        "status_counts": status_counts,
        "recent_total": len(recent_rows),
        "recent_completed": sum(
            1 for task in recent_rows if task.status == TaskStatus.COMPLETED
        ),
        "recent_failed": sum(
            1 for task in recent_rows if task.status == TaskStatus.FAILED
        ),
        "recent_cancelled": sum(
            1 for task in recent_rows if task.status == TaskStatus.CANCELLED
        ),
        "latency_ms_sum": sum(latencies),
        "latency_ms_p95": percentile_ms(latencies, 0.95) or 0,
        "queue_latency_ms_sum": sum(queue_latencies),
        "queue_latency_ms_p95": percentile_ms(queue_latencies, 0.95) or 0,
    }


async def queue_snapshot(
    queue: TaskQueue | None,
    mode: str,
) -> dict[str, Any]:
    if queue is None:
        return {"mode": mode, "enabled": False}
    try:
        metrics = await queue.metrics()
    except Exception:
        return {"mode": mode, "enabled": True, "error": "unavailable"}
    return {"mode": mode, "enabled": True, **metrics}


async def build_observability_snapshot(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    trace_store: TraceStore,
    model_tracer: ModelTracer,
    task_queue: TaskQueue | None,
    task_executor_mode: str,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model_snapshot(model_tracer),
        "traces": trace_snapshot(trace_store),
        "tasks": await task_snapshot(session_factory),
        "queue": await queue_snapshot(task_queue, task_executor_mode),
    }


def _count_by(records: list[Any], key: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = key(record)
        counts[value] = counts.get(value, 0) + 1
    return counts


def _metric(name: str, value: Any, labels: dict[str, str] | None = None) -> str:
    number = _safe_float(value)
    rendered = str(int(number)) if number.is_integer() else str(number)
    if labels:
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}} {rendered}"
    return f"{name} {rendered}"


def prometheus_text(snapshot: dict[str, Any]) -> str:
    lines = [
        "# HELP xzd_task_status_total Task count by current status.",
        "# TYPE xzd_task_status_total gauge",
    ]
    status_counts = snapshot.get("tasks", {}).get("status_counts", {})
    for status, count in sorted(status_counts.items()):
        lines.append(_metric("xzd_task_status_total", count, {"status": status}))

    lines.extend(
        [
            "# HELP xzd_task_recent_total Recent task rows sampled for observability.",
            "# TYPE xzd_task_recent_total gauge",
            _metric(
                "xzd_task_recent_total",
                snapshot.get("tasks", {}).get("recent_total", 0),
            ),
            "# HELP xzd_task_latency_ms_sum Task execution latency sum in ms.",
            "# TYPE xzd_task_latency_ms_sum counter",
            _metric(
                "xzd_task_latency_ms_sum",
                snapshot.get("tasks", {}).get("latency_ms_sum", 0),
            ),
            "# HELP xzd_task_latency_ms_p95 Recent task latency p95 in milliseconds.",
            "# TYPE xzd_task_latency_ms_p95 gauge",
            _metric(
                "xzd_task_latency_ms_p95",
                snapshot.get("tasks", {}).get("latency_ms_p95", 0),
            ),
            "# HELP xzd_task_queue_latency_ms_sum Queue wait latency sum in ms.",
            "# TYPE xzd_task_queue_latency_ms_sum counter",
            _metric(
                "xzd_task_queue_latency_ms_sum",
                snapshot.get("tasks", {}).get("queue_latency_ms_sum", 0),
            ),
        ]
    )

    model = snapshot.get("model", {})
    lines.extend(
        [
            "# HELP xzd_model_call_total Total model calls observed.",
            "# TYPE xzd_model_call_total counter",
            _metric("xzd_model_call_total", model.get("total", 0)),
            "# HELP xzd_model_error_total Total failed model calls observed.",
            "# TYPE xzd_model_error_total counter",
            _metric("xzd_model_error_total", model.get("failed", 0)),
            "# HELP xzd_model_fallback_total Total model fallback calls observed.",
            "# TYPE xzd_model_fallback_total counter",
            _metric("xzd_model_fallback_total", model.get("fallback", 0)),
            "# HELP xzd_model_latency_ms_sum Total model latency in milliseconds.",
            "# TYPE xzd_model_latency_ms_sum counter",
            _metric("xzd_model_latency_ms_sum", model.get("latency_ms_sum", 0)),
            "# HELP xzd_model_prompt_tokens_total Total prompt tokens observed.",
            "# TYPE xzd_model_prompt_tokens_total counter",
            _metric("xzd_model_prompt_tokens_total", model.get("prompt_tokens", 0)),
            "# HELP xzd_model_completion_tokens_total Completion tokens total.",
            "# TYPE xzd_model_completion_tokens_total counter",
            _metric(
                "xzd_model_completion_tokens_total",
                model.get("completion_tokens", 0),
            ),
            "# HELP xzd_model_total_tokens_total Total tokens observed.",
            "# TYPE xzd_model_total_tokens_total counter",
            _metric("xzd_model_total_tokens_total", model.get("total_tokens", 0)),
        ]
    )
    for provider, count in sorted(model.get("by_provider", {}).items()):
        lines.append(
            _metric("xzd_model_provider_calls_total", count, {"provider": provider})
        )
    for model_name, count in sorted(model.get("by_model", {}).items()):
        lines.append(
            _metric("xzd_model_calls_total", count, {"model": model_name})
        )

    queue = snapshot.get("queue", {})
    lines.extend(
        [
            "# HELP xzd_queue_pending Pending task IDs in Redis.",
            "# TYPE xzd_queue_pending gauge",
            _metric("xzd_queue_pending", queue.get("pending", 0)),
            "# HELP xzd_queue_dead_letter Dead-lettered task IDs in Redis.",
            "# TYPE xzd_queue_dead_letter gauge",
            _metric("xzd_queue_dead_letter", queue.get("dead_letter", 0)),
            "# HELP xzd_queue_attempts Task IDs with in-flight delivery attempts.",
            "# TYPE xzd_queue_attempts gauge",
            _metric("xzd_queue_attempts", queue.get("attempts", 0)),
        ]
    )

    traces = snapshot.get("traces", {})
    lines.extend(
        [
            "# HELP xzd_trace_total Total supervisor/graph traces retained.",
            "# TYPE xzd_trace_total gauge",
            _metric("xzd_trace_total", traces.get("total", 0)),
            "# HELP xzd_trace_node_total Total trace nodes retained.",
            "# TYPE xzd_trace_node_total gauge",
            _metric("xzd_trace_node_total", traces.get("node_total", 0)),
        ]
    )
    for status, count in sorted(traces.get("by_route_status", {}).items()):
        lines.append(
            _metric("xzd_trace_route_status_total", count, {"status": status})
        )

    return "\n".join(lines) + "\n"
