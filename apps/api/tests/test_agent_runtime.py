from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from app.agents import AgentRegistry
from app.contracts import (
    AgentRequest,
    Intent,
    RouteDecision,
    RouteStatus,
    TaskRequestContext,
)
from app.core.config import Settings
from app.main import create_app
from app.providers.mock import MockAgentProvider
from app.services.agent_runtime import (
    AgentExecutionPlanner,
    AgentInputMapper,
    ProviderCircuitBreaker,
    WorkflowOutputParserRegistry,
)
from fastapi.testclient import TestClient


def _request(*, intent: Intent = Intent.EXPLAIN_CONCEPT) -> AgentRequest:
    return AgentRequest(
        task_id="task_contract",
        session_id="session_contract",
        user_id="user_contract",
        course_id="CT",
        intent=intent,
        canonical_input={"text": "什么是节点电压法？"},
        options={
            "request_id": "request_contract",
            "retrieved_context": "[E1] 节点电压法证据",
        },
    )


def test_learn_input_mapper_preserves_nine_string_fields() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    request = _request()
    context = TaskRequestContext.from_agent_request(request, input_mode="text")

    mapped = AgentInputMapper().map(
        definition,
        context,
        retrieval_context="[E1] 节点电压法证据",
    )

    assert len(mapped.parameters) == 9
    assert mapped.parameters["AGENT_USER_INPUT"] == "什么是节点电压法？"
    assert mapped.parameters["course_id"] == "CT"
    assert mapped.parameters["retrieved_context"].startswith("[E1]")
    assert all(isinstance(value, str) for value in mapped.parameters.values())
    assert "authorization" not in json.dumps(mapped.redacted_preview).lower()


def test_output_parser_supports_json_fence_and_fixed_lines() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    parser = WorkflowOutputParserRegistry()
    fenced = parser.parse(
        'prefix```json\n{"status":"success","answer":"答案",'
        '"warnings_json":"[]","confidence":"0.8",'
        '"request_id":"request_contract"}\n```suffix',
        definition,
        input_type="text",
    )
    assert fenced.answer_text == "答案"
    assert fenced.confidence == 0.8

    lines = "\n".join(
        [
            "success",
            "CT",
            "explain_concept",
            "固定行答案",
            '["要点"]',
            '["E1"]',
            "[]",
            "0.75",
            "ok",
            "request_contract",
        ]
    )
    fixed = parser.parse(lines, definition, input_type="text")
    assert fixed.answer_text == "固定行答案"
    assert fixed.structured["source_references"] == ["E1"]


def test_execution_plan_is_policy_driven_and_does_not_load_models() -> None:
    registry = AgentRegistry()
    request = _request()
    decision = RouteDecision(
        agent_id="LEARN_01_KNOWLEDGE_QA_V1",
        scene="learning",
        course_id="CT",
        intent=request.intent.value,
        route_status=RouteStatus.SELECTED,
        reason="contract test",
        retrieval_required=True,
        provider_required=True,
    )
    plan = AgentExecutionPlanner(registry, Settings()).build(decision, request)

    assert plan.use_rag is True
    assert plan.retrieval_policy_name == "learn_knowledge_qa"
    assert plan.use_images is True
    assert plan.reranker_mode == "conditional"
    assert plan.budget.local_total_p95_target_ms == 1000


def test_circuit_breaker_opens_and_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"value": 10.0}
    monkeypatch.setattr("app.services.agent_runtime.monotonic", lambda: clock["value"])
    breaker = ProviderCircuitBreaker(failure_threshold=2, reset_seconds=5)
    breaker.record_failure()
    assert breaker.state == "degraded"
    breaker.record_failure()
    assert breaker.state == "open_circuit"
    assert breaker.allow_request() is False
    clock["value"] = 16.0
    assert breaker.state == "recovering"
    assert breaker.allow_request() is True
    assert breaker.allow_request() is False
    breaker.record_success()
    assert breaker.state == "available"


def test_registry_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(
        "scenes:\n  learning: {}\n  learning: {}\nagents:\n  A: {}\n"
        "routing:\n  - {course_ids: [CT], intents: [general_qa], "
        "agent_id: A, scene: learning}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate Agent registry key"):
        AgentRegistry(path)


def test_agent_debug_status_and_dry_run_are_redacted(client: TestClient) -> None:
    status = client.get("/api/v1/agents/status")
    assert status.status_code == 200
    serialized = json.dumps(status.json()).lower()
    assert "authorization" not in serialized
    assert "api_secret" not in serialized

    dry_run = client.post(
        "/api/v1/agents/LEARN_01_KNOWLEDGE_QA_V1/dry-run",
        json={
            "question": "解释戴维南定理",
            "course_id": "CT",
            "intent": "explain_concept",
            "retrieved_context": "[E1] 戴维南定理",
        },
    )
    assert dry_run.status_code == 200
    payload = dry_run.json()
    assert payload["cloud_called"] is False
    assert payload["execution_plan"]["retrieval_policy_name"] == "learn_knowledge_qa"


def test_cloud_failure_uses_agent_configured_local_fallback(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        test_database_url=f"sqlite+aiosqlite:///{tmp_path / 'fallback.db'}",
        default_agent_provider="mock",
        xingchen_enabled=True,
        xingchen_api_key="test-key",
        xingchen_api_secret="test-secret",
        xingchen_knowledge_qa_flow_id="test-learn-flow",
        knowledge_enabled=False,
        knowledge_ct_path=tmp_path / "knowledge" / "CT",
        knowledge_ae_path=tmp_path / "knowledge" / "AE",
        knowledge_de_path=tmp_path / "knowledge" / "DE",
        local_storage_path=tmp_path / "storage",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as local_client:
        mock_provider = MockAgentProvider()
        local_client.app.state.provider = mock_provider
        local_client.app.state.task_runner.provider = mock_provider
        session = local_client.post(
            "/api/v1/sessions",
            json={"user_id": "fallback-user", "course_id": "CT"},
        ).json()
        created = local_client.post(
            "/api/v1/tasks",
            json={
                "session_id": session["id"],
                "user_id": "fallback-user",
                "scene": "learning",
                "course_id": "CT",
                "intent": "general_qa",
                "canonical_input": {"question": "解释KCL"},
                "options": {"mock_force_failure": True},
            },
        )
        assert created.status_code == 202
        task_id = created.json()["id"]
        deadline = time.monotonic() + 5
        task: dict[str, object] = {}
        while time.monotonic() < deadline:
            task = local_client.get(f"/api/v1/tasks/{task_id}").json()
            if task.get("status") in {"completed", "failed"}:
                break
            time.sleep(0.02)

    assert task["status"] == "completed"
    assert task["agent_id"] == "LEARN_01_LOCAL_RETRIEVAL_V1"
    result = task["result_content"]
    assert isinstance(result, dict)
    assert result["structured_result"]["fallback_used"] is True
    assert result["structured_result"]["fallback_reason"] == "provider_error"
