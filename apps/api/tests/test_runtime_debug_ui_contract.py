from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEBUG_ROOT = ROOT / "apps" / "api" / "app" / "static" / "debug"


def _read(name: str) -> str:
    return (DEBUG_ROOT / name).read_text(encoding="utf-8")


def test_runtime_control_markup_declares_safe_actions() -> None:
    html = _read("execution.html")

    assert 'id="runtime-controls"' in html
    assert 'data-runtime-action="pause"' in html
    assert 'data-runtime-action="resume"' in html
    assert 'data-runtime-action="approve"' in html
    assert "最终权限与状态由后端校验" in html


def test_runtime_control_script_keeps_actions_state_aware_and_backend_owned() -> None:
    script = _read("execution.js")

    assert 'pause: new Set(["created", "queued", "running"])' in script
    assert 'resume: new Set(["paused", "waiting_input"])' in script
    assert 'approve: new Set(["waiting_approval"])' in script
    assert '"/pause"' not in script
    assert '"/resume"' not in script
    assert '"/approve"' not in script
    assert "${action}${query}" in script
    assert 'const payload = { decision: "approved" }' in script
    assert "runtime_run_id" in script


def test_runtime_polling_is_finite_and_stops_at_terminal_states() -> None:
    script = _read("execution.js")

    assert 'const runtimePollDelaysMs = [1000, 2000, 4000, 8000, 16000]' in script
    assert "runtimePollAttempts >= runtimePollDelaysMs.length" in script
    assert 'function runtimeNeedsPolling(data)' in script
    assert 'runtimePollStatuses.has(runtimeStatusKey(data?.runtime?.status))' in script
    assert "stopRuntimePolling()" in script
