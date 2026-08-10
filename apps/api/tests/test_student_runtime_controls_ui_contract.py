from __future__ import annotations

from pathlib import Path


def _static_root() -> Path:
    return Path(__file__).parents[1] / "app" / "static" / "debug"


def test_student_page_exposes_runtime_control_markup_and_status_copy() -> None:
    script = (_static_root() / "student.js").read_text(encoding="utf-8")

    for value in (
        "student-runtime-controls",
        "student-runtime-pause",
        "student-runtime-resume",
        "student-runtime-approve",
        "student-runtime-input-form",
        "student-runtime-reject-proposal",
        "/runtime-controls",
        "function runtimeApprovalAllowed()",
        "return false;",
        "waiting_approval: \"等待人工审批\"",
        "expected_state_version: runtimeTaskControls?.state_version",
        "state.activeTaskWait?.cancel()",
        "state.runSequence === requestSequence",
    ):
        assert value in script


def test_student_sse_reconnect_keeps_eventsource_cursor_and_reconciles_controls(
) -> None:
    script = (_static_root() / "student.js").read_text(encoding="utf-8")
    error_block = script.split("events.onerror = () => {", 1)[1].split("};", 1)[0]

    assert "Last-Event-ID" in error_block
    assert "events.close()" not in error_block
    assert "pollTimer = setInterval(finish, 900)" in error_block
    assert "refreshRuntimeTaskControls(id)" in error_block


def test_student_runtime_controls_have_responsive_layout_styles() -> None:
    css = (_static_root() / "pages.css").read_text(encoding="utf-8")

    assert ".student-runtime-controls" in css
    assert ".student-runtime-actions" in css
    assert ".student-runtime-input textarea" in css
