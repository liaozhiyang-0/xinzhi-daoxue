from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps" / "api" / "app" / "static" / "debug" / "execution.js"


def _read_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_waiting_input_surface_is_status_gated_and_explanatory() -> None:
    script = _read_script()

    assert "function runtimeWaitingInputSurface(runtime)" in script
    assert 'runtimeStatusKey(runtime?.status) !== "waiting_input"' in script
    assert '"用户提示", runtimeSafePrompt(runtime)' in script
    assert '["state_version", runtime.state_version]' in script
    assert '["可恢复", resumable]' in script
    assert 'runtime.resumable === false' in script
    assert '"恢复边界"' in script
    assert "waitingInputSurface ? [waitingInputSurface] : []" in script


def test_waiting_input_prompt_is_bounded_and_uses_only_public_prompt_fields() -> None:
    script = _read_script()

    assert "function runtimeSafePrompt(runtime)" in script
    assert "runtime?.user_prompt" in script
    assert "runtime?.input_prompt" in script
    assert "waiting.prompt" in script
    assert "decision.user_prompt" in script
    assert 'replace(/[\\u0000-\\u001f\\u007f]/g, "")' in script
    assert ".slice(0, 2_000)" in script
    assert "request_snapshot" not in script


def test_existing_runtime_control_boundaries_remain_state_aware() -> None:
    script = _read_script()

    assert 'pause: new Set(["created", "queued", "running"])' in script
    assert 'resume: new Set(["paused", "waiting_input"])' in script
    assert 'approve: new Set(["waiting_approval"])' in script
    assert 'const payload = { decision: "approved" }' in script
    assert "expected_state_version" in script
    assert 'method: "POST"' in script
