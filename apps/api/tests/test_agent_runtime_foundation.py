from __future__ import annotations

import asyncio

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


def test_compaction_creates_versioned_summary_without_extra_model_call(
    api, app
) -> None:
    app.state.settings.context_summary_message_trigger = 4
    app.state.settings.context_recent_message_limit = 2
    session = api.create_session()
    for _ in range(2):
        task = api.create_task(session["id"])
        completed = api.wait_for_task(task["id"])
    assert completed["result_content"]["metrics"]["compaction_count"] == 1
    baseline_model_calls = completed["result_content"]["metrics"]["model_calls"]

    third = api.create_task(session["id"])
    third_completed = api.wait_for_task(third["id"])
    metrics = third_completed["result_content"]["metrics"]
    assert metrics["session_summary_used"] is True
    assert metrics["summary_version"] == 1
    assert metrics["model_calls"] == baseline_model_calls


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
