"""Run the publishable runtime stability benchmark without retaining answers."""

# The script adds the local API package to sys.path before importing it.
# ruff: noqa: E402

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.evaluation.cache import (  # type: ignore[import-untyped]
    EvaluationCache,
    evaluation_fingerprint,
)
from app.evaluation.contracts import (  # type: ignore[import-untyped]
    EvaluationCase,
    EvaluationErrorType,
    FailureStage,
)
from app.evaluation.runner import (  # type: ignore[import-untyped]
    EvaluationRunner,
    evaluation_timeout_decision,
)
from app.main import create_app  # type: ignore[import-untyped]
from run_evaluation import evaluation_settings  # type: ignore[import-not-found]

CASE_PATH = ROOT / "evaluation" / "runtime_stability" / "cases.json"
CASE_ATTACHMENT_ROOT = ROOT / "evaluation" / "cases"
CACHE_ROOT = ROOT / "evaluation" / "cache"
DEFAULT_OUTPUT = ROOT / "docs" / "runtime_hardening" / "runtime_baseline.json"
MODES = ("local_mock", "local_deterministic")
GENERAL_LATENCY_BUDGET_MS = 15_000
COMPLEX_LATENCY_BUDGET_MS = 60_000
COMPLEX_CATEGORIES = frozenset({"multi_turn", "multimodal", "research", "solver"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行时稳定性基准执行器")
    parser.add_argument("--mode", choices=(*MODES, "both"), default="both")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=150)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--representative-count", type=int, default=48)
    parser.add_argument("--representative-only", action="store_true")
    parser.add_argument(
        "--include-representative-repeat",
        action="store_true",
        help="在完整批次之外追加 48 案例 × 3 轮重复结果",
    )
    return parser.parse_args()


def load_catalog() -> tuple[list[EvaluationCase], dict[str, str], str]:
    payload = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    cases = [EvaluationCase.model_validate(item) for item in payload["cases"]]
    categories = {
        str(key): str(value) for key, value in payload["case_categories"].items()
    }
    return cases, categories, str(payload.get("source_catalog_sha256", ""))


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _first_sse_projection(
    task_created_at: Any,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    created = _parse_time(task_created_at)
    if not events:
        return {
            "event_count": 0,
            "first_event_type": "",
            "first_event_latency_ms": None,
            "first_content_event_type": "",
            "first_content_event_latency_ms": None,
            "ttft_ms": None,
            "ttft_measurement": "unavailable",
            "completion_event_latency_ms": None,
        }
    first = _parse_time(events[0].get("created_at"))
    completion = next(
        (item for item in events if item.get("event_type") == "task_completed"),
        None,
    )
    completion_time = _parse_time(completion.get("created_at")) if completion else None
    def event_data(item: dict[str, Any]) -> dict[str, Any]:
        payload = item.get("event_data")
        if not isinstance(payload, dict):
            return {}
        nested = payload.get("data")
        return nested if isinstance(nested, dict) else payload

    content_event = next(
        (item for item in events if event_data(item).get("content_available") is True),
        None,
    )
    content_time = (
        _parse_time(content_event.get("created_at")) if content_event else None
    )

    def delta_ms(value: datetime | None) -> float | None:
        if created is None or value is None:
            return None
        return round(max(0.0, (value - created).total_seconds() * 1000), 3)

    return {
        "event_count": len(events),
        "first_event_type": str(events[0].get("event_type", "")),
        "first_event_latency_ms": delta_ms(first),
        "first_content_event_type": (
            str(content_event.get("event_type", "")) if content_event else ""
        ),
        "first_content_event_latency_ms": delta_ms(content_time),
        "ttft_ms": delta_ms(content_time),
        "ttft_measurement": (
            "first_content_available" if content_event else "unavailable"
        ),
        "completion_event_latency_ms": delta_ms(completion_time),
    }


async def _events(runner: EvaluationRunner, task_id: str) -> list[dict[str, Any]]:
    assert runner.client is not None
    response = await runner.client.get(f"/api/v1/tasks/{task_id}/events")
    response.raise_for_status()
    values = response.json()
    return [item for item in values if isinstance(item, dict)]


def _safe_trace(actual: dict[str, Any]) -> dict[str, Any]:
    structured = actual.get("structured_result")
    if not isinstance(structured, dict):
        return {}
    trace = structured.get("runtime_timing")
    if not isinstance(trace, dict):
        return {}
    return {
        "schema_version": trace.get("schema_version", ""),
        "run_id": trace.get("run_id", ""),
        "stages": trace.get("stages", {}),
        "fingerprints": trace.get("fingerprints", {}),
        "counters": trace.get("counters", {}),
        "context_usage": trace.get("context_usage", {}),
        "event_count": len(trace.get("events", []))
        if isinstance(trace.get("events"), list)
        else 0,
        "events": [
            {
                "event": item.get("event", ""),
                "at": item.get("at", ""),
                "duration_ms": item.get("duration_ms"),
                "details": {
                    key: value
                    for key, value in (item.get("details") or {}).items()
                    if key
                    in {
                        "node_id",
                        "handler_id",
                        "status",
                        "task_type",
                        "provider",
                        "model",
                        "retry_count",
                        "result_status",
                        "response_usable",
                        "answer_changed",
                    }
                },
            }
            for item in trace.get("events", [])
            if isinstance(item, dict)
        ],
    }


def _record(
    *,
    case: EvaluationCase,
    category: str,
    repeat_index: int,
    result: Any,
    actual: dict[str, Any],
    task: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    structured = actual.get("structured_result")
    structured = structured if isinstance(structured, dict) else {}
    stable_structured = {
        key: value
        for key, value in structured.items()
        if key not in {"runtime_timing", "reflection", "presentation"}
    }
    task = task or {}
    metrics = actual.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    runtime_timing = _safe_trace(actual)
    counters = runtime_timing.get("counters", {})
    counters = counters if isinstance(counters, dict) else {}
    model_call_count = int(
        counters.get("model_call_count", metrics.get("model_calls", 0)) or 0
    )
    tool_call_count = int(
        counters.get("tool_call_count", metrics.get("tool_calls", 0)) or 0
    )
    rag_call_count = int(
        counters.get("rag_call_count", metrics.get("retrieval_calls", 0)) or 0
    )
    retry_count = int(
        counters.get("retry_count", metrics.get("retry_count", 0)) or 0
    )
    fallback_count = int(counters.get("fallback_count", 0) or 0)
    if fallback_count == 0 and actual.get("fallback_used"):
        fallback_count = 1
    stages = runtime_timing.get("stages", {})
    stages = stages if isinstance(stages, dict) else {}
    stage_durations = {
        str(name): float(stage.get("duration_ms", 0) or 0)
        for name, stage in stages.items()
        if isinstance(stage, dict)
        and isinstance(stage.get("duration_ms"), (int, float))
    }
    slowest_stage = (
        max(stage_durations, key=lambda name: stage_durations[name])
        if stage_durations
        else None
    )
    gate_events = [
        event
        for event in runtime_timing.get("events", [])
        if isinstance(event, dict)
    ]
    gate_decision: dict[str, Any] = next(
        (
            event.get("details", {})
            for event in gate_events
            if event.get("event") == "quality_gate_decision"
            and isinstance(event.get("details"), dict)
        ),
        {},
    )
    sse_projection = _first_sse_projection(task.get("created_at"), events)
    runtime_events = runtime_timing.get("events", [])
    tool_ids = sorted(
        {
            str(event.get("details", {}).get("handler_id", ""))
            for event in runtime_events
            if event.get("event") == "tool_end"
            and event.get("details", {}).get("handler_id")
        }
    )
    if not tool_ids:
        selected_tools = actual.get("selected_tools")
        if isinstance(selected_tools, list):
            tool_ids = sorted(str(item) for item in selected_tools if str(item))
    semantic_projection = {
        "status": actual.get("status", ""),
        "agent_id": actual.get("agent_id", ""),
        "execution_path": actual.get("execution_path", ""),
        "course_pack": actual.get("course_pack", structured.get("course")),
        "problem_type": actual.get("problem_type", structured.get("problem_type")),
        "verification_status": actual.get("verification_status"),
        "consistency_status": structured.get("consistency_status"),
        "evidence_status": structured.get("evidence_status"),
    }
    conclusion_projection = {
        "key_equations": structured.get("key_equations"),
        "solution_method": structured.get("solution_method"),
        "verification": structured.get("verification"),
        "verification_report": structured.get("verification_report"),
        "numeric_comparisons": actual.get("numeric_comparisons"),
    }
    rag_stages = runtime_timing.get("stages", {})
    rag_active = bool(
        (runtime_timing.get("counters") or {}).get("rag_call_count", 0)
        or rag_stages.get("rag_retrieval")
        or structured.get("rag_status")
    )
    actions = (case.task_options or {}).get("_evaluation_follow_up_actions")
    turns = (case.structured_input or {}).get("turns")
    turn_count = 1
    if isinstance(turns, list) and turns:
        turn_count = len(turns)
    if isinstance(actions, list):
        turn_count += len(actions)
    degradation_signals = sorted(
        {
            token
            for warning in actual.get("warnings", [])
            for token in ("degraded", "fallback", "timeout", "unavailable")
            if token in str(warning).casefold()
        }
    )
    latency_class = (
        "complex" if category in COMPLEX_CATEGORIES else "general"
    )
    latency_budget_ms = (
        COMPLEX_LATENCY_BUDGET_MS
        if latency_class == "complex"
        else GENERAL_LATENCY_BUDGET_MS
    )
    ttft_ms = sse_projection.get("ttft_ms")
    return {
        "case_id": case.case_id,
        "category": category,
        "course": case.course,
        "repeat_index": repeat_index,
        "status": result.status,
        "total_score": result.total_score,
        "elapsed_ms": result.elapsed_ms,
        "agent_id": actual.get("agent_id", ""),
        "execution_path": actual.get("execution_path", ""),
        "route_status": actual.get("route_status", ""),
        "fallback_used": bool(actual.get("fallback_used", False)),
        "metrics": {
            key: metrics.get(key)
            for key in (
                "latency_ms",
                "total_latency_ms",
                "queue_latency_ms",
                "route_latency_ms",
                "retrieval_latency_ms",
                "context_latency_ms",
                "model_latency_ms",
                "verification_latency_ms",
                "model_calls",
                "tool_calls",
                "retrieval_calls",
                "retry_count",
            )
            if key in metrics
        },
        "model_call_count": model_call_count,
        "tool_call_count": tool_call_count,
        "rag_call_count": rag_call_count,
        "retry_count": retry_count,
        "fallback_count": fallback_count,
        "structured_fingerprint": _hash(stable_structured),
        "output_signature": _hash(
            {
                "semantic": semantic_projection,
                "conclusion": conclusion_projection,
                "tool_activation": tool_ids,
                "rag_activation": rag_active,
                "evidence_signature": _hash(actual.get("citations", [])),
            }
        ),
        "sse": sse_projection,
        "semantic_signature": _hash(semantic_projection),
        "conclusion_signature": _hash(conclusion_projection),
        "answer_conclusion_signature": _hash(
            {
                "semantic": semantic_projection,
                "conclusion": conclusion_projection,
            }
        ),
        "tool_activation": tool_ids,
        "rag_activation": rag_active,
        "evidence_signature": _hash(actual.get("citations", [])),
        "scenario_signature": _hash(
            {
                "agent": actual.get("agent_id", ""),
                "course": actual.get("course_pack", ""),
                "execution_path": actual.get("execution_path", ""),
            }
        ),
        "multi_turn_turn_count": turn_count,
        "multi_turn_context_exercised": turn_count > 1,
        "multi_turn_context_retained": bool(
            task.get("_evaluation_session_reused", False)
        ),
        "degradation_signals": degradation_signals,
        "runtime_timing": runtime_timing,
        "task_status": str(task.get("status", "")),
        "scenario": category,
        "ttft_ms": sse_projection.get("ttft_ms"),
        "latency_budget": {
            "class": latency_class,
            "budget_ms": latency_budget_ms,
            "total_passed": float(result.elapsed_ms) <= latency_budget_ms,
            "ttft_passed": (
                ttft_ms is None or float(ttft_ms) <= latency_budget_ms
            ),
            "measurement_scope": "provider_free_runtime_chain",
        },
        "slowest_stage": slowest_stage,
        "gate_observation": {
            "triggered": bool(stages.get("quality_gate")),
            "response_usable": gate_decision.get("response_usable"),
            "answer_changed": gate_decision.get("answer_changed"),
        },
    }


async def run_one(
    runner: EvaluationRunner,
    case: EvaluationCase,
    category: str,
    repeat_index: int,
) -> dict[str, Any]:
    started = perf_counter()
    trace_id = f"stability_{case.case_id}_{repeat_index}_{uuid4().hex[:8]}"
    before_traces = len(runner.app.state.model_tracer.list())
    timeout_seconds, complexity_signals = evaluation_timeout_decision(case)
    cache_key = runner.cache.key(case, mode=runner.mode)
    try:
        async with asyncio.timeout(timeout_seconds):
            task = await runner._execute(case, trace_id)
        model_calls = runner._model_calls_since(before_traces, trace_id)
        actual = runner._observation(task)
        actual["evaluation_timeout_seconds"] = timeout_seconds
        actual["evaluation_complexity_signals"] = complexity_signals
        assert runner.scorer is not None
        result = runner.scorer.score(
            case,
            actual,
            elapsed_ms=int((perf_counter() - started) * 1000),
            model_calls=model_calls,
            trace_id=trace_id,
            cache_key=cache_key,
        )
        events = await _events(runner, str(task["id"]))
        return _record(
            case=case,
            category=category,
            repeat_index=repeat_index,
            result=result,
            actual=actual,
            task=task,
            events=events,
        )
    except TimeoutError:
        result = runner._terminal_result(
            case,
            status="timeout",
            stage=FailureStage.TIMEOUT,
            error=EvaluationErrorType.TIMEOUT,
            elapsed_ms=int((perf_counter() - started) * 1000),
            trace_id=trace_id,
            cache_key=cache_key,
            mode=runner.mode,
            warning=f"timeout_seconds={timeout_seconds}",
            model_calls=runner._model_calls_since(before_traces, trace_id),
            timeout_seconds=timeout_seconds,
            complexity_signals=complexity_signals,
        )
        return _record(
            case=case,
            category=category,
            repeat_index=repeat_index,
            result=result,
            actual=result.actual,
            task=None,
            events=[],
        )
    except Exception as exc:
        result = runner._terminal_result(
            case,
            status="error",
            stage=FailureStage.UNKNOWN,
            error=EvaluationErrorType.EXECUTION_ERROR,
            elapsed_ms=int((perf_counter() - started) * 1000),
            trace_id=trace_id,
            cache_key=cache_key,
            mode=runner.mode,
            warning=f"{type(exc).__name__}: {str(exc)[:160]}",
        )
        return _record(
            case=case,
            category=category,
            repeat_index=repeat_index,
            result=result,
            actual=result.actual,
            task=None,
            events=[],
        )


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) * fraction + 0.999999) - 1)))
    return round(ordered[index], 3)


def latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "p50_ms": None,
            "p90_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "p50_ms": percentile(values, 0.50),
        "p90_ms": percentile(values, 0.90),
        "p95_ms": percentile(values, 0.95),
        "max_ms": round(max(values), 3),
        "mean_ms": round(sum(values) / len(values), 3),
    }


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    def values(items: list[dict[str, Any]], key: str = "elapsed_ms") -> list[float]:
        return [
            float(item[key])
            for item in items
            if isinstance(item.get(key), (int, float))
        ]

    categories: dict[str, list[dict[str, Any]]] = {}
    courses: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        categories.setdefault(str(item["category"]), []).append(item)
        courses.setdefault(str(item["course"]), []).append(item)
    stage_samples: dict[str, list[float]] = {}
    for item in records:
        stages = item.get("runtime_timing", {}).get("stages", {})
        if not isinstance(stages, dict):
            continue
        for name, stage in stages.items():
            if isinstance(stage, dict) and isinstance(
                stage.get("duration_ms"), (int, float)
            ):
                stage_samples.setdefault(str(name), []).append(
                    float(stage["duration_ms"])
                )
    statuses: dict[str, int] = {}
    for item in records:
        status = str(item.get("status", ""))
        statuses[status] = statuses.get(status, 0) + 1
    ttft_values = [
        float(item["sse"]["ttft_ms"])
        for item in records
        if isinstance(item.get("sse", {}).get("ttft_ms"), (int, float))
    ]
    content_latency_values = [
        float(item["sse"]["first_content_event_latency_ms"])
        for item in records
        if isinstance(
            item.get("sse", {}).get("first_content_event_latency_ms"),
            (int, float),
        )
    ]
    fallback_count = sum(bool(item.get("fallback_used")) for item in records)
    retry_count = sum(
        int(item.get("metrics", {}).get("retry_count", 0) or 0) > 0
        for item in records
    )
    approval_count = sum(
        any(
            str(event.get("event", "")).endswith("approval_required")
            for event in item.get("runtime_timing", {}).get("events", [])
            if isinstance(event, dict)
        )
        for item in records
    )
    degradation_signal_counts: dict[str, int] = {}
    unexpected_degradation_count = 0
    for item in records:
        signals = {
            str(signal) for signal in item.get("degradation_signals", [])
        }
        for signal in signals:
            degradation_signal_counts[signal] = (
                degradation_signal_counts.get(signal, 0) + 1
            )
        if signals.difference({"fallback", "unavailable"}):
            unexpected_degradation_count += 1
    count_totals = {
        key: sum(int(item.get(key, 0) or 0) for item in records)
        for key in (
            "model_call_count",
            "tool_call_count",
            "rag_call_count",
            "retry_count",
            "fallback_count",
        )
    }
    gate_observations = [
        item.get("gate_observation", {})
        for item in records
        if isinstance(item.get("gate_observation"), dict)
    ]
    gate_triggered = sum(bool(item.get("triggered")) for item in gate_observations)
    gate_failed = sum(
        item.get("response_usable") is False for item in gate_observations
    )
    gate_changed = sum(item.get("answer_changed") is True for item in gate_observations)

    latency_budgets: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        budget = item.get("latency_budget")
        if isinstance(budget, dict):
            latency_budgets.setdefault(
                str(budget.get("class", "unknown")), []
            ).append(item)

    latency_budget_metrics: dict[str, Any] = {}
    for latency_class, items in sorted(latency_budgets.items()):
        budget_values = [
            item.get("latency_budget", {}).get("budget_ms")
            for item in items
            if isinstance(item.get("latency_budget", {}).get("budget_ms"), (int, float))
        ]
        passed = sum(
            item.get("latency_budget", {}).get("total_passed") is True
            for item in items
        )
        latency_budget_metrics[latency_class] = {
            "budget_ms": budget_values[0] if budget_values else None,
            "count": len(items),
            "passed": passed,
            "failed": len(items) - passed,
            "pass_rate": round(passed / len(items), 6) if items else 0.0,
            "latency_ms": latency_summary(values(items)),
            "ttft_ms": latency_summary(
                [
                    float(item["ttft_ms"])
                    for item in items
                    if isinstance(item.get("ttft_ms"), (int, float))
                ]
            ),
        }

    def stage_metric_values(name: str) -> list[float]:
        return [
            float(
                item.get("runtime_timing", {})
                .get("stages", {})
                .get(name, {})
                .get("duration_ms", 0)
                or 0
            )
            for item in records
            if isinstance(
                item.get("runtime_timing", {}).get("stages", {}).get(name), dict
            )
        ]

    timing_ms = {
        "T_request_prepare": latency_summary(
            stage_metric_values("request_preparation")
        ),
        "T_route": latency_summary(stage_metric_values("routing")),
        "T_plan": latency_summary(stage_metric_values("planner")),
        "T_context": latency_summary(stage_metric_values("context_build")),
        "T_rag": latency_summary(stage_metric_values("rag")),
        "T_model": latency_summary(stage_metric_values("model")),
        "T_tool": latency_summary(stage_metric_values("tool")),
        "T_reflection": latency_summary(stage_metric_values("reflection")),
        "T_quality_gate": latency_summary(stage_metric_values("quality_gate")),
        "T_math": latency_summary(stage_metric_values("math_postprocess")),
        "T_commit": latency_summary(
            [
                sum(
                    float(
                        item.get("runtime_timing", {})
                        .get("stages", {})
                        .get(stage, {})
                        .get("duration_ms", 0)
                        or 0
                    )
                    for stage in ("session_commit", "result_commit")
                )
                for item in records
            ]
        ),
        "T_sse": latency_summary(
            [
                float(item["sse"]["first_event_latency_ms"])
                for item in records
                if isinstance(
                    item.get("sse", {}).get("first_event_latency_ms"),
                    (int, float),
                )
            ]
        ),
    }
    return {
        "run_count": len(records),
        "case_count": len({item["case_id"] for item in records}),
        "status_counts": statuses,
        "pass_rate": round(
            sum(item.get("status") == "passed" for item in records) / len(records),
            6,
        )
        if records
        else 0.0,
        "latency_ms": latency_summary(values(records)),
        "by_category": {
            key: latency_summary(values(items))
            for key, items in sorted(categories.items())
        },
        "by_course": {
            key: latency_summary(values(items))
            for key, items in sorted(courses.items())
        },
        "stage_latency_ms": {
            key: latency_summary(item_values)
            for key, item_values in sorted(stage_samples.items())
        },
        "timing_ms": timing_ms,
        **count_totals,
        "average_model_calls": round(
            count_totals["model_call_count"] / len(records), 6
        )
        if records
        else 0.0,
        "average_tool_calls": round(
            count_totals["tool_call_count"] / len(records), 6
        )
        if records
        else 0.0,
        "average_rag_calls": round(
            count_totals["rag_call_count"] / len(records), 6
        )
        if records
        else 0.0,
        "average_retry_count": round(
            count_totals["retry_count"] / len(records), 6
        )
        if records
        else 0.0,
        "average_fallback_count": round(
            count_totals["fallback_count"] / len(records), 6
        )
        if records
        else 0.0,
        "gate_metrics": {
            "trigger_rate": round(gate_triggered / len(records), 6) if records else 0.0,
            "fail_rate": round(gate_failed / len(records), 6) if records else 0.0,
            "retry_rate": None,
            "changed_answer_rate": round(gate_changed / len(records), 6)
            if records
            else 0.0,
            "retry_measurement": "not separately emitted by current gate contract",
        },
        "sse_first_event_latency_ms": latency_summary(
            [
                float(item["sse"]["first_event_latency_ms"])
                for item in records
                if isinstance(
                    item.get("sse", {}).get("first_event_latency_ms"), (int, float)
                )
            ]
        ),
        "sse_first_content_latency_ms": latency_summary(content_latency_values),
        "ttft_ms": latency_summary(ttft_values),
        "ttft_measurement": "first_content_available_event",
        "fallback_rate": round(fallback_count / len(records), 6) if records else 0.0,
        "retry_rate": round(retry_count / len(records), 6) if records else 0.0,
        "approval_rate": round(approval_count / len(records), 6) if records else 0.0,
        "unexpected_degradation_rate": (
            round(unexpected_degradation_count / len(records), 6) if records else 0.0
        ),
        "degradation_signal_counts": degradation_signal_counts,
        "latency_budgets": latency_budget_metrics,
    }


def stability_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        groups.setdefault(str(item["case_id"]), []).append(item)
    repeated = [items for items in groups.values() if len(items) > 1]
    if not repeated:
        return {"case_count": 0, "exact_output_stability": None}
    output_stable = [
        len({item["output_signature"] for item in items}) == 1 for items in repeated
    ]
    route_stable = [
        len({(item["agent_id"], item["execution_path"]) for item in items}) == 1
        for items in repeated
    ]
    status_stable = [len({item["status"] for item in items}) == 1 for items in repeated]
    ranges = [
        max(float(item["elapsed_ms"]) for item in items)
        - min(float(item["elapsed_ms"]) for item in items)
        for items in repeated
    ]
    multi_turn_records = [
        item for item in records if int(item.get("multi_turn_turn_count", 1) or 1) > 1
    ]
    multi_turn_cases = {
        str(item["case_id"])
        for item in multi_turn_records
    }
    multi_turn_5plus_cases = {
        str(item["case_id"])
        for item in multi_turn_records
        if int(item.get("multi_turn_turn_count", 1) or 1) >= 5
    }

    def stable(key: str) -> float:
        values = [
            len(
                {
                    json.dumps(item.get(key), sort_keys=True, default=str)
                    for item in items
                }
            )
            == 1
            for items in repeated
        ]
        return round(sum(values) / len(values), 6) if values else 0.0

    return {
        "case_count": len(repeated),
        "repetition_count": sum(len(items) for items in repeated),
        "task_success_rate": round(
            sum(item.get("status") == "passed" for item in records) / len(records),
            6,
        )
        if records
        else 0.0,
        "exact_output_stability": round(sum(output_stable) / len(output_stable), 6),
        "route_stability": round(sum(route_stable) / len(route_stable), 6),
        "routing_consistency": round(sum(route_stable) / len(route_stable), 6),
        "status_stability": round(sum(status_stable) / len(status_stable), 6),
        "agent_consistency": stable("agent_id"),
        "course_consistency": stable("course"),
        "scenario_consistency": stable("scenario_signature"),
        "tool_activation_consistency": stable("tool_activation"),
        "rag_activation_consistency": stable("rag_activation"),
        "evidence_consistency": stable("evidence_signature"),
        "semantic_conclusion_consistency": stable("semantic_signature"),
        "answer_conclusion_consistency": stable("answer_conclusion_signature"),
        "numerical_conclusion_consistency": stable("conclusion_signature"),
        "multi_turn_context_retention": stable("multi_turn_context_retained"),
        "multi_turn_case_count": len(multi_turn_cases),
        "multi_turn_5plus_case_count": len(multi_turn_5plus_cases),
        "degradation_consistency": stable("degradation_signals"),
        "fallback_rate": round(
            sum(bool(item.get("fallback_used")) for item in records) / len(records),
            6,
        )
        if records
        else 0.0,
        "retry_rate": round(
            sum(
                int(item.get("metrics", {}).get("retry_count", 0) or 0) > 0
                for item in records
            )
            / len(records),
            6,
        )
        if records
        else 0.0,
        "approval_rate": round(
            sum(
                any(
                    str(event.get("event", "")).endswith("approval_required")
                    for event in item.get("runtime_timing", {}).get("events", [])
                    if isinstance(event, dict)
                )
                for item in records
            )
            / len(records),
            6,
        )
        if records
        else 0.0,
        "latency_range_ms": latency_summary(ranges),
        "unstable_case_ids": [
            items[0]["case_id"]
            for items in repeated
            if len({item["output_signature"] for item in items}) != 1
        ][:20],
    }


def select_representatives(
    cases: list[EvaluationCase], categories: dict[str, str], count: int
) -> list[EvaluationCase]:
    by_category: dict[str, dict[str, list[EvaluationCase]]] = {}
    for case in cases:
        category = categories[case.case_id]
        by_category.setdefault(category, {}).setdefault(case.course, []).append(case)
    category_courses: dict[str, list[str]] = {}
    category_order: list[str] = []
    for case in cases:
        category = categories[case.case_id]
        if category not in category_order:
            category_order.append(category)
        category_courses.setdefault(category, sorted(by_category[category]))

    buckets: dict[str, list[EvaluationCase]] = {}
    for category in category_order:
        courses = category_courses[category]
        while any(by_category[category].get(course) for course in courses):
            for course in courses:
                values = by_category[category].get(course, [])
                if values:
                    buckets.setdefault(category, []).append(values.pop(0))

    selected: list[EvaluationCase] = []
    while len(selected) < count:
        progressed = False
        for category in category_order:
            values = buckets.get(category, [])
            if values:
                selected.append(values.pop(0))
                progressed = True
            if len(selected) >= count:
                break
        if not progressed:
            break
    return selected


def _result_records(result: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        item
        for item in result.get("records", [])
        if isinstance(item, dict)
    ]
    representative_repeat = result.get("representative_repeat")
    if isinstance(representative_repeat, dict):
        records.extend(_result_records(representative_repeat))
    return records


def _quality_failures(result: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        item
        for item in _result_records(result)
        if item.get("status") != "passed"
    ]
    return records


def _operational_failures(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return task-chain failures, independent of provider answer quality.

    Provider-free modes intentionally produce degraded or fallback answers.
    Those are quality observations, not Runtime transport failures. A missing
    terminal task, malformed timing envelope, or non-completed task remains a
    hard stability failure.
    """

    return [
        item
        for item in _result_records(result)
        if item.get("task_status") != "completed"
        or not isinstance(item.get("runtime_timing"), dict)
        or item.get("runtime_timing", {}).get("schema_version")
        != "runtime_timing.v1"
    ]


def _latency_failures(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _result_records(result)
        if isinstance(item.get("latency_budget"), dict)
        and item["latency_budget"].get("total_passed") is False
    ]


async def run_mode(
    mode: str,
    cases: list[EvaluationCase],
    categories: dict[str, str],
    *,
    repeat: int,
    representative_count: int,
    representative_only: bool,
) -> dict[str, Any]:
    settings = evaluation_settings(live=False)
    run_token = uuid4().hex[:10]
    database = CACHE_ROOT / f"runtime-stability-{mode}-{run_token}.db"
    settings.test_database_url = f"sqlite+aiosqlite:///{database}"
    settings.qdrant_local_path = (
        CACHE_ROOT / f"runtime-stability-{mode}-{run_token}-qdrant"
    )
    app = create_app(settings)
    cache = EvaluationCache(CACHE_ROOT, fingerprint=evaluation_fingerprint(ROOT))
    async with EvaluationRunner(
        app,
        mode=mode,  # type: ignore[arg-type]
        cache=cache,
        report_root=ROOT / "evaluation" / "reports",
        use_cache=False,
    ) as runner:
        runner._case_attachment_root = CASE_ATTACHMENT_ROOT
        # Offline stability measures execution latency, not one-time index
        # construction. Prepare the lexical corpus once before the first case,
        # matching the production startup warmup path.
        if settings.knowledge_enabled:
            await asyncio.to_thread(runner.app.state.knowledge_base.refresh)
        selected = (
            select_representatives(cases, categories, representative_count)
            if representative_only
            else cases
        )
        records: list[dict[str, Any]] = []
        for repeat_index in range(1, repeat + 1):
            for index, case in enumerate(selected, 1):
                records.append(
                    await run_one(runner, case, categories[case.case_id], repeat_index)
                )
                print(
                    f"mode={mode} repeat={repeat_index}/{repeat} "
                    f"case={index}/{len(selected)} id={case.case_id}"
                )
        return {
            "mode": mode,
            "repeat": repeat,
            "representative_only": representative_only,
            "records": records,
            "aggregate": aggregate(records),
            "stability": stability_summary(records),
            "top_slow_cases": sorted(
                (
                    {
                        "case_id": item["case_id"],
                        "category": item["category"],
                        "course": item["course"],
                        "elapsed_ms": item["elapsed_ms"],
                        "status": item["status"],
                    }
                    for item in records
                ),
                key=lambda item: float(item["elapsed_ms"]),
                reverse=True,
            )[:20],
        }


async def main() -> None:
    args = parse_args()
    if args.limit < 1 or args.repeat < 1 or args.representative_count < 1:
        raise ValueError("limit、repeat、representative-count 必须为正整数")
    cases, categories, source_hash = load_catalog()
    cases = cases[: args.limit]
    selected_modes = MODES if args.mode == "both" else (args.mode,)
    results = {}
    for mode in selected_modes:
        full_result = await run_mode(
            mode,
            cases,
            categories,
            repeat=args.repeat,
            representative_count=min(args.representative_count, len(cases)),
            representative_only=args.representative_only,
        )
        if args.include_representative_repeat and not args.representative_only:
            full_result["representative_repeat"] = await run_mode(
                mode,
                cases,
                categories,
                repeat=3,
                representative_count=min(args.representative_count, len(cases)),
                representative_only=True,
            )
        results[mode] = full_result
    output = {
        "schema_version": "runtime_benchmark.v1",
        "case_catalog": str(CASE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "case_catalog_sha256": source_hash,
        "case_count": len(cases),
        "modes": results,
        "raw_prompts_stored": False,
        "raw_answers_stored": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    quality_failures = {
        mode: len(_quality_failures(result))
        for mode, result in results.items()
        if _quality_failures(result)
    }
    operational_failures = {
        mode: len(_operational_failures(result))
        for mode, result in results.items()
        if _operational_failures(result)
    }
    latency_failures = {
        mode: len(_latency_failures(result))
        for mode, result in results.items()
        if _latency_failures(result)
    }
    output["gate"] = {
        "status": "failed" if operational_failures or latency_failures else "passed",
        "scope": "runtime_protocol_and_latency_budget",
        "operational_failures": operational_failures,
        "latency_failures": latency_failures,
        "quality_failures": quality_failures,
        "quality_disposition": (
            "informational_provider_free_mode"
            if quality_failures
            else "none"
        ),
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"output={args.output}")
    if operational_failures:
        print(
            "runtime stability gate failed: "
            + json.dumps(operational_failures, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1)
    if latency_failures:
        print(
            "runtime latency budget gate failed: "
            + json.dumps(latency_failures, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1)
    if quality_failures:
        print(
            "runtime protocol gate passed; provider-free quality failures recorded: "
            + json.dumps(quality_failures, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )


if __name__ == "__main__":
    asyncio.run(main())
