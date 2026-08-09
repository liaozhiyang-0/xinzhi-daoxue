from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps" / "api" / "app" / "static" / "debug" / "agents.js"


def _read() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_agents_ui_consumes_optional_runtime_capability_contract() -> None:
    script = _read()

    assert 'Array.isArray(value) ? value.filter' in script
    for field in (
        "capability_id", "domain", "runtime_id", "version", "enabled",
        "supported_actions", "supports_pause", "supports_resume",
        "supports_approval", "supports_input", "status", "result_contract",
        "control_scope",
    ):
        assert field in script
    assert "runtimeCapabilitiesDetails" in script
    assert "capabilities.length" in script


def test_agents_ui_groups_top_level_capabilities_by_runtime_domain() -> None:
    script = _read()

    assert 'const runtimeCapabilityDomains = { task_agent:' in script
    assert 'learning_loop:' in script
    assert "function runtimeCapabilityDomainGroups(value)" in script
    assert "runtimeCapabilityDomainDetails" in script
    assert 'data-capability-domain' in script
    assert "control_scope：" in script
    assert "supported_actions：" in script
    assert "runtimeCapabilitiesFromAgentPayload" in script


def test_agents_ui_does_not_add_readiness_api_or_control_calls() -> None:
    script = _read()

    assert 'api("/api/v1/agents/runtime-readiness"' not in script
    assert "runtimeCapabilitiesFromAgentPayload(data, state.agents)" in script
    assert "method: \"POST\"" in script


def test_agents_ui_handles_malformed_capabilities_without_throwing() -> None:
    script = _read()

    assert "function safeRuntimeCapabilityList(value)" in script
    assert "if (!capabilities.length)" in script
    assert 'typeof item === "object" && !Array.isArray(item)' in script
    assert "runtimeCapabilitiesDetails(readiness.runtime_capabilities)" in script


def test_agents_ui_redacts_sensitive_or_path_like_capability_values() -> None:
    script = _read()

    assert 'function safeRuntimeCapabilityText(value, fallback = "未提供")' in script
    assert "secret|token|password|credential|api[_-]?key|bearer" in script
    assert "text.length > 160" in script
    assert 'replace(/[\\u0000-\\u001f\\u007f]/g, "")' in script


def test_agents_ui_keeps_existing_agent_api_and_actions() -> None:
    script = _read()

    assert 'api("/api/v1/agents"' in script
    assert 'api(`/api/v1/agents/${encodeURIComponent(id)}`)' in script
    assert "const paths = { validate:" in script
