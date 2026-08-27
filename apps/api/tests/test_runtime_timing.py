from datetime import UTC, datetime

from app.observability import ModelCallRecord, RuntimeTimingTrace, timed_stage


def test_runtime_timing_trace_is_bounded_and_metadata_only() -> None:
    options: dict[str, object] = {}
    RuntimeTimingTrace.begin(
        options,
        task_id="task-1",
        request_id="request-1",
        trace_id="trace-1",
    )
    with timed_stage(options, "planner"):
        pass
    RuntimeTimingTrace.fingerprint(options, "plan_hash", {"node": "answer"})
    RuntimeTimingTrace.increment(options, "model_call_count")

    snapshot = RuntimeTimingTrace.snapshot(options)

    assert snapshot["schema_version"] == "runtime_timing.v1"
    assert snapshot["task_id"] == "task-1"
    assert snapshot["stages"]["planner"]["count"] == 1
    assert snapshot["stages"]["planner"]["outcome"] == "completed"
    assert len(snapshot["fingerprints"]["plan_hash"]) == 64
    assert snapshot["counters"]["model_call_count"] == 1
    assert all("answer" not in event for event in snapshot["events"])


def test_runtime_timing_records_model_metadata_without_payloads() -> None:
    options: dict[str, object] = {}
    RuntimeTimingTrace.begin(
        options,
        task_id="task-2",
        request_id="request-2",
        trace_id="trace-2",
    )
    RuntimeTimingTrace.record_model_calls(
        options,
        [
            ModelCallRecord(
                trace_id="trace-2",
                request_id="request-2",
                provider="dashscope",
                model="qwen-test",
                task_type="academic_problem_solving",
                start_time=datetime.now(UTC),
                elapsed_ms=12,
                status="completed",
                retry_count=1,
                fallback_used=True,
                input_hash="input-hash",
            )
        ],
    )

    snapshot = RuntimeTimingTrace.snapshot(options)

    assert snapshot["stages"]["model_call_1"]["duration_ms"] == 12.0
    assert snapshot["counters"]["model_call_count"] == 1
    assert snapshot["counters"]["retry_count"] == 1
    assert snapshot["counters"]["fallback_count"] == 1
    assert snapshot["fingerprints"]["model_input_hash_1"]
    assert all(
        "qwen-test" in event.get("details", {}).values()
        for event in snapshot["events"]
        if event["event"] == "model_call_1_end"
    )
