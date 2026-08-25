from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contracts import ExecutionStatus, NodeTrace
from app.observability import (
    ModelCallRecord,
    ModelTracer,
    TraceProjectionService,
    TraceStore,
)


def test_trace_projection_groups_spans_and_redacts_sensitive_summaries() -> None:
    store = TraceStore()
    trace_id = "trace-projection"
    started = datetime(2026, 8, 25, tzinfo=UTC)
    nodes = [
        NodeTrace(
            node_name="identify_course",
            start_time=started,
            end_time=started + timedelta(milliseconds=4),
            elapsed_ms=4,
            status=ExecutionStatus.SUCCESS,
            input_summary={"message": "private question", "input_type": "text"},
            output_summary={"course": "CT"},
        ),
        NodeTrace(
            node_name="rag_retrieve",
            start_time=started,
            end_time=started + timedelta(milliseconds=12),
            elapsed_ms=12,
            status=ExecutionStatus.SUCCESS,
            output_summary={"tool_id": "rag.retrieve", "chunks": 2},
        ),
        NodeTrace(
            node_name="verify_answer",
            start_time=started,
            end_time=started + timedelta(milliseconds=7),
            elapsed_ms=7,
            status=ExecutionStatus.SUCCESS,
            output_summary={"answer": "private answer", "passed": True},
        ),
    ]
    state = {
        "trace_id": trace_id,
        "run_id": "run-projection",
        "request_id": "request-projection",
        "course": "CT",
        "intent": "solve_problem",
        "task_family": "ACADEMIC_SOLVING",
        "selected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "route_status": "success",
        "warnings": [],
        "errors": [],
        "trace": nodes,
    }
    store.put(state)  # type: ignore[arg-type]
    model_tracer = ModelTracer()
    model_tracer.record(
        ModelCallRecord(
            trace_id=trace_id,
            request_id="request-projection",
            provider="local",
            model="mock-solver",
            task_type="solve",
            start_time=started,
            elapsed_ms=25,
            status="completed",
            retry_count=0,
            fallback_used=False,
        )
    )

    projection = TraceProjectionService(store, model_tracer).project(trace_id)

    assert projection is not None
    spans = projection["spans"]
    assert [item["span_type"] for item in spans] == [
        "ingress",
        "retrieval",
        "verification",
        "model",
    ]
    assert spans[1]["tool_id"] == "rag.retrieve"
    assert spans[0]["input_summary"] == {"input_type": "text"}
    assert "answer" not in spans[2]["output_summary"]
    assert spans[-1]["duration_ms"] == 25


def test_trace_projection_returns_none_for_expired_or_unknown_trace() -> None:
    service = TraceProjectionService(TraceStore(), ModelTracer())

    assert service.project("missing-trace") is None
