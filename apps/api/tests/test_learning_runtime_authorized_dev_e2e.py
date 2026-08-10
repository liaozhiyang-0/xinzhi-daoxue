from __future__ import annotations

from scripts.run_learning_runtime_authorized_dev_e2e import (
    event_summary,
    redact,
    runtime_summary,
    selected_cases,
)


def test_selected_learning_cases_are_deterministic() -> None:
    cases = selected_cases(["teaching_request_more_hint"])
    assert [case.case_id for case in cases] == ["teaching_request_more_hint"]
    assert cases[0].action == "request_more_hint"


def test_learning_e2e_redaction_removes_sensitive_values() -> None:
    payload = redact({"api_key": "secret-value", "nested": {"token": "x"}})
    assert payload == {
        "api_key": "[redacted]",
        "nested": {"token": "[redacted]"},
    }


def test_learning_e2e_event_summary_detects_sequence_regression() -> None:
    summary = event_summary(
        [{"sequence": 1}, {"sequence": 3}, {"sequence": 2}]
    )
    assert summary["count"] == 3
    assert summary["strictly_increasing"] is False


def test_learning_e2e_runtime_summary_keeps_only_safe_node_fields() -> None:
    summary = runtime_summary(
        {
            "status": "completed",
            "run_kind": "teaching_interaction",
            "state_version": 4,
            "approval_required": False,
            "resumable": False,
            "available_controls": [],
            "node_statuses": [
                {
                    "node_id": "teaching.feedback.verify",
                    "status": "succeeded",
                    "effect_status": "completed",
                    "attempt": 1,
                    "error_code": "",
                    "raw_prompt": "must-not-be-copied",
                },
                {
                    "node_id": "bad node",
                    "status": "failed",
                    "effect_status": "failed",
                    "attempt": 1,
                    "error_code": "bad code",
                },
            ],
        }
    )
    assert summary["node_statuses"] == [
        {
            "node_id": "teaching.feedback.verify",
            "status": "succeeded",
            "effect_status": "completed",
            "attempt": 1,
            "error_code": "",
        },
        {
            "node_id": None,
            "status": "failed",
            "effect_status": "failed",
            "attempt": 1,
            "error_code": "",
        },
    ]
