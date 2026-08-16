from __future__ import annotations


def test_knowledge_question_uses_course_routing_and_local_evidence(
    api, settings, client
) -> None:
    settings.knowledge_ae_path.mkdir(parents=True, exist_ok=True)
    (settings.knowledge_ae_path / "switching-regulator.md").write_text(
        "# 开关稳压电路\n"
        "开关稳压电路利用高频开关、储能元件和反馈调节输出电压。",
        encoding="utf-8",
    )
    session = api.create_session(user_id="knowledge-web-user")
    response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": session["id"],
            "user_id": "knowledge-web-user",
            "user_role": "student",
            "scene": "learning",
            "course_id": "UNKNOWN",
            "intent": "unknown",
            "canonical_input": {"text": "讲解一下开关稳压电路"},
            "options": {"allow_cloud": False, "response_depth": "standard"},
        },
    )
    assert response.status_code == 202, response.text

    task = api.wait_for_task(response.json()["id"])
    result = task["result_content"]
    structured = result["structured_result"]

    assert task["status"] == "completed"
    assert task["agent_id"] == "LEARN_01_KNOWLEDGE_QA_V1"
    assert task["course_id"] == "AE"
    assert task["intent"] == "explain_concept"
    assert result["citations"]
    assert "本地资料依据" in result["answer"]
    assert structured["presentation"]["source_summary"] != "未使用外部材料"
