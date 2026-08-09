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


def test_learning_runtime_ui_renders_backend_control_contract_read_only() -> None:
    script = _read_script()

    assert '"runtime_id"' in script
    assert '"status"' in script
    assert '"control_scope"' in script
    assert '"available_controls"' in script
    assert "function learningRuntimeStatusSurface(reference)" in script
    assert "if (learningRuntimeReference(data))" in script
    assert "panel.hidden = true" in script
    assert "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}" in script
    assert (
        "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/approve"
        not in script
    )
    assert "data-learning-runtime-action" not in script


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
    assert "if (learningRuntimeReference(data))" in script
    assert "panel.hidden = true" in script
    assert (
        "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/pause"
        not in script
    )
    assert (
        "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/resume"
        not in script
    )
    assert (
        "/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/approve"
        not in script
    )
