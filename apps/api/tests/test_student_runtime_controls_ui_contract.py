from __future__ import annotations

from pathlib import Path


def _static_root() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "static" / "debug"


def test_student_page_exposes_runtime_control_markup_and_status_copy() -> None:
    script = (_static_root() / "student.js").read_text(encoding="utf-8")
    tasks = script

    for value in (
        "student-runtime-controls",
        "student-runtime-pause",
        "student-runtime-resume",
        "student-runtime-approve",
        "student-runtime-input-form",
    ):
        assert value in script
    assert "/runtime-controls" in tasks
    assert "refreshRuntimeTaskControls" in tasks
    assert "runtimeTaskControlUrl" in tasks
    assert "/${taskId}/${action}" in tasks
    for action in ("pause", "resume", "approve", "input"):
        assert f'"{action}"' in tasks


def test_student_sse_reconnect_keeps_eventsource_cursor_and_reconciles_controls(
) -> None:
    script = (_static_root() / "ts" / "task-transport.js").read_text(encoding="utf-8")
    error_block = script.split("events.onerror = () => {", 1)[1].split("};", 1)[0]

    assert "Last-Event-ID" in error_block
    assert "events.close()" not in error_block
    assert "refreshRuntimeTaskControls(id)" in error_block
    assert "reconnectPollTimer = window.setInterval" in error_block


def test_student_runtime_controls_have_responsive_layout_styles() -> None:
    css = (_static_root() / "pages.css").read_text(encoding="utf-8")

    assert ".student-runtime-controls" in css
    assert ".student-runtime-input" in css


def test_student_submission_clears_input_before_task_creation() -> None:
    script = (_static_root() / "workspace.js").read_text(encoding="utf-8")
    submission = script.split("async function submit", 1)[1]
    assert '$("#question-input").value = ""' in submission
    assert '$("#student-attempt-input").value = ""' in submission
