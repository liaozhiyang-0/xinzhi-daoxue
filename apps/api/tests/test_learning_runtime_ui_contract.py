from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps" / "api" / "app" / "static" / "debug" / "execution.js"
HTML = ROOT / "apps" / "api" / "app" / "static" / "debug" / "execution.html"


def _read_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_execution_debug_ui_recognizes_learning_runtime_references() -> None:
    script = _read_script()

    assert "function learningRuntimeReference(data)" in script
    assert "data?.runtime_run_id" in script
    assert "runtime.runtime_run_id" in script
    assert '"teaching_interaction", "learning_progress"' in script
    assert "encodeURIComponent(reference.runId)" in script
    assert "/api/v1/learning/runtime/" in script


def test_learning_runtime_ui_renders_backend_control_contract_and_actions() -> None:
    script = _read_script()

    assert '"runtime_id"' in script
    assert '"status"' in script
    assert '"control_scope"' in script
    assert '"available_controls"' in script
    assert "projection?.controls" in script
    assert "entry?.reason_code" in script
    assert "function learningRuntimeControlProjection(reference)" in script
    assert (
        "function learningRuntimeControlActionAvailable(projection, action)"
        in script
    )
    assert "function learningRuntimeControlStateVersion(projection)" in script
    assert "function learningRuntimeControlEntry(projection, action)" in script
    assert 'status === "waiting_approval"' in script
    assert "entry?.available === true" in script
    assert "function learningRuntimeStatusSurface(reference)" in script
    assert "function renderLearningRuntimeControls(reference)" in script
    assert (
        "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/controls"
        in script
    )
    assert (
        "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/control"
        in script
    )
    assert (
        "function executeLearningRuntimeControl(action = \"approve\", "
        "inputData = null)"
        in script
    )
    assert 'function executeLearningRuntimeControl(action = "approve", ' in script
    assert "expected_state_version: expectedStateVersion" in script
    assert '...(action === "input" ? { data } : {})' in script
    assert 'idempotency_key: `execution_${action}_${crypto.randomUUID()}`' in script
    assert "loadLearningRuntimeStatus(execution, true)" in script
    assert "loadLearningRuntimeControls(execution, true)" in script
    assert "request_snapshot" not in script


def test_learning_runtime_ui_submits_only_backend_exposed_controls() -> None:
    script = _read_script()
    html = HTML.read_text(encoding="utf-8")

    assert "Only actions exposed by the backend checkpoint are enabled." in script
    assert "learningRuntimeControlActionAvailable(projection, action)" in script
    assert 'if (action === "input")' in script
    assert "data = { text }" in script
    assert 'executeLearningRuntimeControl("input")' in script
    assert 'id="runtime-input-form"' in html
    assert 'id="runtime-input"' in html
    assert 'id="runtime-input-submit"' in html


def test_learning_runtime_ui_renders_status_contract_and_redacted_node_statuses(
) -> None:
    script = _read_script()

    assert "function learningRuntimeNodeStatusSurface(nodes)" in script
    assert "Array.isArray(nodes)" in script
    assert "node.node_id" in script
    assert "node.status" in script
    assert "node.effect_status" in script
    assert "node.attempt" in script
    assert "node.error_code" in script
    assert '["goal", snapshot.goal]' in script
    assert '["success_criteria", snapshot.success_criteria]' in script
    assert '["state_version", snapshot.state_version]' in script
    assert '["resumable", snapshot.resumable]' in script
    assert '["approval_required", snapshot.approval_required]' in script
    assert "snapshot.node_statuses" in script
    assert '"No LearningLoop node status reported."' in script


def test_learning_runtime_ui_keeps_legacy_task_controls_separate() -> None:
    script = _read_script()

    assert "const isLearningLoop = hasInlineLearningRuntime" in script
    assert "const learningReference = learningRuntimeReference(data)" in script
    assert "/api/v1/tasks/${encodeURIComponent(id)}/${action}${query}" in script
    assert 'panel.dataset.learningRuntime = "false"' in script
    assert "runtimeControlAllowedStatuses[action]" in script
