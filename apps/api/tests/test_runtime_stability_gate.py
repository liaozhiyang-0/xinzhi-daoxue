from scripts.run_runtime_stability import (
    _latency_failures,
    _operational_failures,
    _quality_failures,
)


def _record(*, status: str = "passed", task_status: str = "completed") -> dict:
    return {
        "status": status,
        "task_status": task_status,
        "runtime_timing": {"schema_version": "runtime_timing.v1"},
    }


def test_provider_free_quality_failure_does_not_fail_runtime_protocol_gate() -> None:
    result = {"records": [_record(status="failed")]}

    assert len(_quality_failures(result)) == 1
    assert _operational_failures(result) == []


def test_incomplete_task_chain_fails_runtime_protocol_gate() -> None:
    result = {"records": [_record(task_status="failed")]}

    assert len(_operational_failures(result)) == 1


def test_representative_repeat_is_included_in_both_diagnostics() -> None:
    result = {
        "records": [_record()],
        "representative_repeat": {
            "records": [_record(status="failed", task_status="failed")]
        },
    }

    assert len(_quality_failures(result)) == 1
    assert len(_operational_failures(result)) == 1


def test_latency_budget_failure_is_a_hard_gate_failure() -> None:
    result = {
        "records": [
            {
                **_record(),
                "latency_budget": {
                    "class": "general",
                    "budget_ms": 15_000,
                    "total_passed": False,
                },
            }
        ]
    }

    assert len(_latency_failures(result)) == 1
