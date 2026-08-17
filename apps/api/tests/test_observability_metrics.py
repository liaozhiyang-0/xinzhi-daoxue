from __future__ import annotations

from app.observability.metrics import model_snapshot, prometheus_text, trace_snapshot
from app.observability.model_tracer import ModelCallRecord, ModelTracer
from app.observability.tracer import TraceStore


def test_model_snapshot_counts_metrics() -> None:
    tracer = ModelTracer(max_records=10)
    tracer.record(
        ModelCallRecord(
            trace_id="t1",
            request_id="r1",
            provider="dashscope",
            model="qwen3.5-flash",
            task_type="intent_classification",
            start_time=tracer.now(),
            elapsed_ms=12,
            status="completed",
            retry_count=0,
            fallback_used=False,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )
    tracer.record(
        ModelCallRecord(
            trace_id="t2",
            request_id="r2",
            provider="dashscope",
            model="qwen3.7-plus",
            task_type="academic_problem_solving",
            start_time=tracer.now(),
            elapsed_ms=20,
            status="failed",
            retry_count=1,
            fallback_used=True,
            error_type="provider_error",
        )
    )

    snapshot = model_snapshot(tracer)
    assert snapshot["total"] == 2
    assert snapshot["completed"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["fallback"] == 1
    assert snapshot["latency_ms_sum"] == 32
    assert snapshot["prompt_tokens"] == 10
    assert snapshot["by_provider"]["dashscope"] == 2


def test_trace_snapshot_counts_route_status() -> None:
    store = TraceStore(max_records=10)
    store._records["trace-1"] = {
        "trace_id": "trace-1",
        "route_status": "success",
        "selected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "course": "CT",
        "nodes": [{"node": "a"}, {"node": "b"}],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    snapshot = trace_snapshot(store)
    assert snapshot["total"] == 1
    assert snapshot["node_total"] == 2
    assert snapshot["by_route_status"]["success"] == 1
    assert snapshot["by_selected_agent"]["ACADEMIC_PROBLEM_SOLVER"] == 1


def test_prometheus_text_contains_core_metric_families() -> None:
    snapshot = {
        "tasks": {
            "status_counts": {"completed": 3, "failed": 1},
            "recent_total": 4,
            "latency_ms_sum": 100,
            "latency_ms_p95": 50,
            "queue_latency_ms_sum": 20,
            "queue_latency_ms_p95": 10,
        },
        "model": {
            "total": 5,
            "failed": 1,
            "fallback": 1,
            "latency_ms_sum": 200,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "by_provider": {"dashscope": 5},
        },
        "traces": {
            "total": 2,
            "node_total": 3,
            "by_route_status": {"success": 2},
        },
        "queue": {
            "mode": "redis",
            "enabled": True,
            "pending": 1,
            "dead_letter": 0,
            "attempts": 0,
        },
    }

    text = prometheus_text(snapshot)
    assert "xzd_task_status_total{status=\"completed\"} 3" in text
    assert "xzd_model_call_total 5" in text
    assert "xzd_queue_pending 1" in text
    assert "xzd_trace_total 2" in text
