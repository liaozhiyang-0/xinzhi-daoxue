from __future__ import annotations

from pathlib import Path


def _static_root() -> Path:
    return Path(__file__).resolve().parents[3] / "apps" / "web" / "src"


def test_student_page_exposes_runtime_control_markup_and_status_copy() -> None:
    script = (_static_root() / "app" / "App.tsx").read_text(encoding="utf-8")
    tasks = (_static_root() / "api" / "tasks.ts").read_text(encoding="utf-8")

    for value in (
        "task-controls",
        "runtimeControls.pause",
        "runtimeControls.resume",
        "runtimeControls.approve",
        "runtimeControls.input",
    ):
        assert value in script
    assert "/runtime-controls" in tasks
    assert "getTaskRuntimeControls" in tasks
    assert "/approve" in tasks
    assert "/input" in tasks


def test_student_sse_reconnect_keeps_eventsource_cursor_and_reconciles_controls(
) -> None:
    script = (_static_root() / "task-transport.ts").read_text(encoding="utf-8")
    error_block = script.split("events.onerror = () => {", 1)[1].split("};", 1)[0]

    assert "Last-Event-ID" in error_block
    assert "events.close()" not in error_block
    assert "refreshRuntimeTaskControls(id)" in error_block


def test_student_runtime_controls_have_responsive_layout_styles() -> None:
    css = (_static_root() / "styles" / "app.css").read_text(encoding="utf-8")

    assert ".task-controls" in css
    assert ".runtime-input" in css
    assert ".workspace-drawer-scrim" in css
