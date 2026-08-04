from __future__ import annotations

from datetime import UTC
from typing import Any

from app.models import TaskModel


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_value(sources: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def bounded_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def result_sources(task: TaskModel) -> list[dict[str, Any]]:
    result = _as_dict(task.result_content)
    structured = _as_dict(result.get("structured_result"))
    retrieval = _as_dict(structured.get("retrieval"))
    summary = _as_dict(structured.get("execution_summary"))
    metrics = _as_dict(result.get("metrics"))
    return [result, structured, retrieval, summary, metrics]


def task_latency_ms(task: TaskModel) -> int | None:
    if task.started_at is not None and task.completed_at is not None:
        started = task.started_at
        completed = task.completed_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=UTC)
        return max(0, int((completed - started).total_seconds() * 1000))
    return bounded_int(
        first_value(result_sources(task), ("latency_ms", "total_latency_ms"))
    )


def task_queue_latency_ms(task: TaskModel) -> int | None:
    if task.started_at is not None:
        started = task.started_at
        created = task.created_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return max(0, int((started - created).total_seconds() * 1000))
    return bounded_int(first_value(result_sources(task), ("queue_latency_ms",)))


def percentile_ms(values: list[int], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return float(ordered[index])
