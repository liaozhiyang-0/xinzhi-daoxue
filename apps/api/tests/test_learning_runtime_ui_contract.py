from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps" / "api" / "app" / "static" / "debug" / "execution.js"


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


def test_learning_runtime_ui_renders_backend_control_contract_and_approval_action() -> None:
    script = _read_script()

    assert '"runtime_id"' in script
    assert '"status"' in script
    assert '"control_scope"' in script
    assert '"available_controls"' in script
    assert "projection?.controls" in script
    assert "entry?.reason_code" in script
    assert "function learningRuntimeControlProjection(reference)" in script
    assert "function learningRuntimeApproveAvailable(reference, projection)" in script
    assert "status === \"waiting_approval\"" in script
    assert "entry?.available === true" in script
    assert "function learningRuntimeStatusSurface(reference)" in script
    assert "function renderLearningRuntimeControls(reference)" in script
    assert "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/controls" in script
    assert "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/control" in script
    assert "function executeLearningRuntimeControl()" in script
    assert 'action: "approve"' in script
    assert "expected_state_version: expectedStateVersion" in script
    assert "loadLearningRuntimeStatus(execution, true)" in script
    assert "loadLearningRuntimeControls(execution, true)" in script
    assert "request_snapshot" not in script
    assert "敏感请求快照不在此处展示" in script


def test_learning_runtime_ui_rejects_unsupported_controls_without_requests() -> None:
    script = _read_script()

    assert 'const rejected = action !== "approve"' in script
    assert "不会从此页面发送请求" in script
    assert "pause / resume / input 当前由 LearningLoop 后端拒绝或未实现" in script
    assert 'if (action === "approve") return executeLearningRuntimeControl();' in script
    assert 'if (action === "approve") return executeLearningRuntimeControl();\n    return;' in script
    assert "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/input" not in script


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


def test_learning_runtime_ui_keeps_learning_controls_read_only_for_legacy_payloads(
) -> None:
    script = _read_script()

    assert "const isLearningLoop = inline != null" in script
    assert "const learningReference = learningRuntimeReference(data)" in script
    assert "/api/v1/tasks/${encodeURIComponent(id)}/${action}${query}" in script
    assert "panel.dataset.learningRuntime = \"false\"" in script
    assert "runtimeControlAllowedStatuses[action]" in script
