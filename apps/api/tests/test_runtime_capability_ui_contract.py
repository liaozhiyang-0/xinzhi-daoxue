from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps" / "api" / "app" / "static" / "debug" / "agents.js"


def _read() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_agents_ui_consumes_optional_runtime_capability_contract() -> None:
    script = _read()

    assert "Array.isArray(value) ? value.filter" in script
    for field in (
        "capability_id",
        "domain",
        "runtime_id",
        "version",
        "enabled",
        "supported_actions",
        "supports_pause",
        "supports_resume",
        "supports_approval",
        "supports_input",
        "status",
        "result_contract",
        "control_scope",
        "structural_release_eligible",
        "semantic_release_eligible",
        "canary_release_eligible",
        "canary_reason",
        "blockers",
    ):
        assert field in script
    assert "runtimeCapabilitiesDetails" in script
    assert "capabilities.length" in script


def test_agents_ui_groups_top_level_capabilities_by_runtime_domain() -> None:
    script = _read()

    assert "const runtimeCapabilityDomains = { task_agent:" in script
    assert "learning_loop:" in script
    assert "function runtimeCapabilityDomainGroups(value)" in script
    assert "runtimeCapabilityDomainDetails" in script
    assert "data-capability-domain" in script
    assert "control_scope：" in script
    assert "supported_actions：" in script
    assert "runtimeCapabilitiesFromAgentPayload" in script


def test_agents_ui_projects_capability_evidence_fail_closed() -> (
    None
):
    script = _read()

    assert "function runtimeCapabilityEvidence(capability)" in script
    assert 'safeRuntimeCapabilityText(capability.status, "未报告")' in script
    assert 'typeof capability.canary_release_eligible === "boolean"' in script
    assert "capability.canary_release_eligible === true" in script
    assert 'safeRuntimeCapabilityText(capability.canary_reason, "未报告")' in script
    assert 'blockersLabel: blockers === null ? "未报告"' in script
    assert "runtimeCapabilityEvidenceBadges" in script
    assert "runtimeCapabilityEvidenceDetails" in script
    assert "执行状态：" in script
    assert "Canary 发布资格：" in script
    assert "发布阻塞项：" in script


def test_agents_ui_does_not_add_readiness_api_or_control_calls() -> None:
    script = _read()

    assert 'api("/api/v1/agents/runtime-readiness"' not in script
    assert "runtimeCapabilitiesFromAgentPayload(data, state.agents)" in script
    assert 'method: "POST"' in script


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
    assert "api(`/api/v1/agents/${encodeURIComponent(id)}`)" in script
    assert "const paths = { validate:" in script


def test_agents_ui_projects_read_only_publication_evidence_status() -> None:
    script = _read()

    assert "function runtimePublicationEvidence(readiness = {})" in script
    assert "structural_release_eligible" in script
    assert "semantic_release_eligible" in script
    assert "canary_release_eligible" in script
    assert "canary_reason" in script
    assert "configured_launch_mode" in script
    assert "effective_launch_mode" in script
    assert "发布证据状态（只读）" in script
    assert "结构证据未就绪" in script
    assert "语义证据未就绪" in script
    assert "runtimePublicationEvidenceSummary" in script
    assert "data-evidence-state" in script
    assert "publicationAuthorizationReasons" in script
    assert '"release_authorization_missing"' in script
    assert "authorizationBlocked" in script
    assert "publicationReady" in script
    assert 'evidence.publicationReady ? "ready" : "planned"' in script


def test_agents_ui_keeps_publication_evidence_provider_free_and_no_control_post() -> (
    None
):
    script = _read()

    assert 'api("/api/v1/agents/runtime-readiness"' not in script
    assert "function runtimePublicationEvidence(readiness = {})" in script
    assert 'method: "POST"' in script
    assert (
        "Provider"
        not in script.split("function runtimePublicationEvidence", 1)[1].split(
            "function runtimePublicationEvidenceSummary", 1
        )[0]
    )


def test_agents_ui_sanitizes_publication_evidence_text_and_missing_fields() -> None:
    script = _read()

    assert 'function safeRuntimeReadinessText(value, fallback = "未提供")' in script
    assert "function safeRuntimeReadinessItems(value)" in script
    assert "text.length > 160" in script
    assert "secret|token|password|credential|api[_-]?key|bearer" in script
    assert "safeRuntimeReadinessItems(readiness.blockers)" in script
    assert "未提供独立语义通过字段" in script
