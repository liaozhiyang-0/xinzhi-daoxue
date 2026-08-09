from __future__ import annotations

import asyncio
import json
import time

from app.contracts import ModelResponse
from app.contracts.conversation import (
    ContextMessage,
    ConversationContextBundle,
    MessageRole,
)
from app.core.config import Settings
from app.services.context_budget import ContextBudgetManager
from app.services.context_cache import ContextAssemblyCache


def test_task_persists_message_history_and_isolates_users(api) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"
    assert completed["user_message_id"]
    assert completed["assistant_message_id"]
    assert "active_memories" not in completed["input_content"]["options"]

    response = api.client.get(
        f"/api/v1/sessions/{session['id']}/messages",
        params={"user_id": "user-test"},
    )
    assert response.status_code == 200
    messages = response.json()
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert [item["sequence"] for item in messages] == [1, 2]
    assert messages[0]["source_task_id"] == task["id"]
    assert messages[1]["source_task_id"] == task["id"]

    denied = api.client.get(
        f"/api/v1/sessions/{session['id']}/messages",
        params={"user_id": "another-user"},
    )
    assert denied.status_code == 404


def test_shadow_runtime_wraps_legacy_task_without_second_provider_call(
    api, app
) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"

    debug = api.client.get(f"/api/v1/debug/execution/{task['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["run_kind"] == "runtime"
    assert runtime["status"] == "completed"
    assert runtime["goal_contract"]["objective"]
    assert runtime["goal_contract"]["source"] == "request"
    assert len(runtime["nodes"]) == 1
    node = runtime["nodes"][0]
    assert node["node_id"] == "legacy.execution"
    assert node["handler_id"].startswith("legacy.task_runner.")
    assert node["status"] == "succeeded"
    assert node["attempt"] == 1
    assert node["error_code"] == ""
    assert node["runtime_effect"]["reconciliation_id"] == (
        f"runtime:{runtime['run_id']}:legacy.execution"
    )


def test_runtime_control_endpoints_reject_terminal_runs_without_mutation(
    api, app
) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"

    for action in ("pause", "resume", "approve"):
        response = api.client.post(f"/api/v1/tasks/{task['id']}/{action}")
        assert response.status_code == 409


def test_runtime_input_endpoint_rejects_terminal_runs_without_mutation(
    api, app
) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"

    response = api.client.post(
        f"/api/v1/tasks/{task['id']}/input",
        json={"data": {"scope": "2026-Q1"}},
    )
    assert response.status_code == 409


def test_runtime_reconciliation_endpoint_rejects_terminal_runs_without_mutation(
    api, app
) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"

    response = api.client.post(
        f"/api/v1/tasks/{task['id']}/reconcile",
        json={
            "node_id": "legacy.execution",
            "outcome": "succeeded",
            "facts": {"external_status": "confirmed"},
        },
    )
    assert response.status_code == 409


def test_idempotent_task_does_not_duplicate_user_message(api) -> None:
    session = api.create_session()
    options = {"idempotency_key": "runtime-message-key"}
    first = api.create_task(session["id"], options=options)
    second = api.create_task(session["id"], options=options)
    assert second["id"] == first["id"]
    api.wait_for_task(first["id"])

    messages = api.client.get(
        f"/api/v1/sessions/{session['id']}/messages",
        params={"user_id": "user-test"},
    ).json()
    assert [item["role"] for item in messages].count("user") == 1


def test_session_list_search_archive_restore(api) -> None:
    session = api.create_session()
    updated = api.client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"user_id": "user-test", "title": "相量复习"},
    )
    assert updated.status_code == 200

    found = api.client.get(
        "/api/v1/sessions/search",
        params={"user_id": "user-test", "q": "相量"},
    )
    assert [item["id"] for item in found.json()] == [session["id"]]

    archived = api.client.post(
        f"/api/v1/sessions/{session['id']}/archive",
        params={"user_id": "user-test"},
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    recent = api.client.get(
        "/api/v1/sessions", params={"user_id": "user-test"}
    ).json()
    assert session["id"] not in {item["id"] for item in recent}

    restored = api.client.post(
        f"/api/v1/sessions/{session['id']}/restore",
        params={"user_id": "user-test"},
    )
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None


def test_memory_crud_soft_delete_and_session_switch(api) -> None:
    created = api.client.post(
        "/api/v1/memories",
        json={
            "user_id": "user-test",
            "memory_type": "preference",
            "scope": "global",
            "content": "公式使用LaTeX",
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["memory_id"]

    denied = api.client.patch(
        f"/api/v1/memories/{memory_id}",
        json={"user_id": "another-user", "content": "越权修改"},
    )
    assert denied.status_code == 404

    deleted = api.client.delete(
        f"/api/v1/memories/{memory_id}",
        params={"user_id": "user-test"},
    )
    assert deleted.status_code == 200
    assert (
        api.client.get("/api/v1/memories", params={"user_id": "user-test"}).json()
        == []
    )
    restored = api.client.post(
        f"/api/v1/memories/{memory_id}/restore",
        params={"user_id": "user-test"},
    )
    assert restored.status_code == 200
    forgotten = api.client.post(
        "/api/v1/memories/forget",
        json={"user_id": "user-test", "query": "LaTeX"},
    )
    assert forgotten.status_code == 200
    assert forgotten.json()["affected"] == 1
    assert (
        api.client.get("/api/v1/memories", params={"user_id": "user-test"}).json()
        == []
    )

    session = api.create_session()
    disabled = api.client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"user_id": "user-test", "memory_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["memory_enabled"] is False
    assert disabled.json()["auto_memory_enabled"] is False


def test_context_budget_preserves_current_turn(settings: Settings) -> None:
    constrained = settings.model_copy(
        update={
            "context_max_input_tokens": 1000,
            "context_reserved_output_tokens": 256,
        }
    )
    manager = ContextBudgetManager(constrained)
    recent = [
        ContextMessage(
            message_id=f"message-{index}",
            sequence=index,
            role=MessageRole.USER if index % 2 else MessageRole.ASSISTANT,
            content_text=("旧内容" * 400) if index < 4 else "当前问题不能被裁掉",
        )
        for index in range(1, 5)
    ]
    decision = manager.apply(
        fixed_text="用户纠正：电阻应为10欧姆",
        recent_messages=recent,
        older_messages=[],
        memories=[],
    )
    assert decision.trimmed is True
    assert decision.recent_messages[-1].content_text == "当前问题不能被裁掉"
    assert decision.estimation_method == "conservative_chars_div_2"


def test_follow_up_uses_same_session_context_and_explicit_memory(api) -> None:
    session = api.create_session()
    first = api.create_task(session["id"])
    api.wait_for_task(first["id"])
    follow_up_payload = api.task_payload(
        session["id"], intent="unknown", options={"use_local_rag": False}
    )
    follow_up_payload["course_id"] = "AUTO"
    follow_up_payload["canonical_input"] = {"text": "那电流呢？"}
    response = api.client.post("/api/v1/tasks", json=follow_up_payload)
    assert response.status_code == 202, response.text
    follow_up = api.wait_for_task(response.json()["id"])
    assert follow_up["course_id"] == "CT"

    remember_payload = api.task_payload(
        session["id"], intent="unknown", options={"use_local_rag": False}
    )
    remember_payload["canonical_input"] = {"text": "记住公式都使用LaTeX"}
    remember = api.client.post("/api/v1/tasks", json=remember_payload)
    assert remember.status_code == 202
    api.wait_for_task(remember.json()["id"])
    memories = api.client.get(
        "/api/v1/memories", params={"user_id": "user-test"}
    ).json()
    assert any("LaTeX" in item["content"] for item in memories)

    debug = api.client.get(f"/api/v1/debug/execution/{follow_up['id']}")
    assert debug.status_code == 200
    context = debug.json()["performance"]["context"]
    assert context["recent_message_count"] >= 2
    assert context["estimated_tokens"] > 0


def test_auto_memory_opt_in_is_used_by_the_next_task(api) -> None:
    session = api.create_session()
    updated = api.client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={
            "user_id": "user-test",
            "memory_enabled": True,
            "auto_memory_enabled": True,
        },
    )
    assert updated.status_code == 200

    preference = api.task_payload(
        session["id"],
        intent="general_qa",
        options={"use_local_rag": False},
    )
    preference["canonical_input"] = {
        "text": "我希望讲解时先给思路再给答案"
    }
    created = api.client.post("/api/v1/tasks", json=preference)
    assert created.status_code == 202, created.text
    completed = api.wait_for_task(created.json()["id"])
    usage = completed["result_content"]["context_usage"]
    assert usage["memory_action"] == "auto_remembered"
    assert usage["memory_write_count"] == 1

    memories = api.client.get(
        "/api/v1/memories",
        params={"user_id": "user-test"},
    ).json()
    assert len(memories) == 1
    assert memories[0]["content"] == "我希望讲解时先给思路再给答案"
    assert memories[0]["content_data"]["capture_mode"] == "automatic_opt_in"

    follow_up = api.create_task(
        session["id"],
        options={"use_local_rag": False},
    )
    follow_up_completed = api.wait_for_task(follow_up["id"])
    follow_up_usage = follow_up_completed["result_content"]["context_usage"]
    assert follow_up_usage["active_memory_count"] == 1
    assert follow_up_usage["active_memory_ids"] == [memories[0]["memory_id"]]


def test_academic_boundary_preflight_skips_unnecessary_retrieval(api) -> None:
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="solve_problem",
        options={"use_local_rag": True},
    )
    payload["course_id"] = "CT"
    payload["canonical_input"] = {
        "text": "所示电路没有附电路图，缺少元件参数和连接关系，请直接计算。"
    }

    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"])
    result = completed["result_content"]

    assert result["metrics"]["retrieval_calls"] == 0
    assert result["structured_result"]["retrieval_preflight"] == {
        "status": "skipped",
        "reason": "missing_figure",
        "saved_stage": "knowledge_retrieval",
    }


def test_each_completed_answer_runs_background_model_summary_for_next_turn(
    api, app
) -> None:
    class SummaryModel:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def generate_json_for_task(
            self,
            task_type: str,
            *,
            messages: list[dict[str, object]],
            request_id: str,
            schema: object,
        ) -> ModelResponse:
            del messages, schema
            self.calls.append(request_id)
            return ModelResponse(
                provider="test",
                model="summary-test",
                content=json.dumps(
                    {
                        "summary": "用户正在求解电路问题。",
                        "current_goal": "继续完成电路计算",
                        "key_facts": ["题目属于电路理论"],
                        "explicit_user_preferences": [
                            "回答公式统一使用 LaTeX"
                        ],
                        "unresolved_items": ["继续确认电流"],
                    },
                    ensure_ascii=False,
                ),
                elapsed_ms=3,
            )

    summary_model = SummaryModel()
    app.state.session_compaction.model_service = summary_model
    session = api.create_session()
    updated = api.client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={
            "user_id": "user-test",
            "memory_enabled": True,
            "auto_memory_enabled": True,
        },
    )
    assert updated.status_code == 200

    first = api.create_task(session["id"])
    first_completed = api.wait_for_task(first["id"])
    assert first_completed["result_content"]["context_usage"][
        "summary_refresh_status"
    ] in {"queued", "completed"}

    deadline = time.monotonic() + 3
    first_summary = None
    while time.monotonic() < deadline:
        response = api.client.get(
            f"/api/v1/sessions/{session['id']}/summary",
            params={"user_id": "user-test"},
        )
        assert response.status_code == 200
        first_summary = response.json()
        if first_summary is not None:
            break
        time.sleep(0.02)
    assert first_summary["version"] == 1
    assert first_summary["generation_method"] == "model"
    assert first_summary["model_name"] == "summary-test"
    memories = api.client.get(
        "/api/v1/memories",
        params={"user_id": "user-test"},
    ).json()
    assert memories[0]["content"] == "回答公式统一使用 LaTeX"
    assert (
        memories[0]["content_data"]["capture_mode"]
        == "model_summary_explicit_preference"
    )

    second = api.create_task(session["id"])
    second_completed = api.wait_for_task(second["id"])
    metrics = second_completed["result_content"]["metrics"]
    assert metrics["session_summary_used"] is True
    assert metrics["summary_version"] == 1

    deadline = time.monotonic() + 3
    second_summary = first_summary
    while time.monotonic() < deadline:
        second_summary = api.client.get(
            f"/api/v1/sessions/{session['id']}/summary",
            params={"user_id": "user-test"},
        ).json()
        if second_summary["version"] == 2:
            break
        time.sleep(0.02)
    assert second_summary["version"] == 2
    assert len(summary_model.calls) == 2


def test_context_cache_falls_back_to_bounded_memory(settings: Settings) -> None:
    async def exercise() -> None:
        cache = ContextAssemblyCache(settings)
        key = cache.key(
            {
                "session_id": "session-test",
                "session_revision": 1,
                "current_message_id": "message-test",
                "task_family": "general_qa",
                "course_id": "CT",
                "agent_id": "local",
                "context_config_version": "test",
                "memory_revision": 0,
                "summary_version": 0,
                "rag_context_version": "",
            }
        )
        bundle = ConversationContextBundle(
            session_id="session-test",
            token_estimate=10,
            budget=100,
            estimation_method="conservative_chars_div_2",
        )
        backend = await cache.set(key, bundle)
        cached, read_backend = await cache.get(key)
        await cache.close()
        assert backend == "memory"
        assert read_backend == "memory"
        assert cached is not None
        assert cached.token_estimate == 10

    asyncio.run(exercise())
