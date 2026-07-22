from __future__ import annotations

import io

from app.contracts import AgentRequest, Intent
from app.models import SessionModel
from app.services.session_context import SessionContextService
from PIL import Image


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (24, 16), "white").save(output, format="PNG")
    return output.getvalue()


def test_student_page_uses_unified_task_and_event_apis(client) -> None:
    page = client.get("/student")
    script = client.get("/debug-assets/workspace.js")
    styles = client.get("/debug-assets/workspace-v2.css")

    assert page.status_code == 200
    assert "知识问答" in page.text
    assert "自然语言自动调度" in page.text
    assert 'id="mode-control"' not in page.text
    assert "今天想学习什么" in page.text
    assert "Mock形式" not in page.text
    assert "Qdrant" not in page.text
    assert "Flow ID" not in page.text
    assert "Xingchen" not in page.text
    assert "专业工作流" not in page.text
    assert "教案设计" in page.text
    assert "作业初审" in page.text
    assert "学术写作" in page.text
    assert "数据分析" in page.text
    assert 'api("/api/v1/tasks"' in script.text
    assert "/debug/rag/run" not in script.text
    assert "xingchen-api" not in script.text
    assert "new EventSource" in script.text
    assert "task.error_message" in script.text
    assert "云端耗时" not in script.text
    assert "summary.agent_id" not in script.text
    assert "prefer_internal_agents: true" in script.text
    assert "allow_cloud: false" in script.text
    assert 'audience: "student"' in script.text
    assert 'api("/api/v1/capabilities")' in script.text
    assert "/api/v1/sessions/${state.sessionId}/tasks?limit=50" in script.text
    assert "archiveCurrentAnswer()" in script.text
    assert "scrollbar-gutter: stable" in styles.text
    assert ".workspace-center" in styles.text and "min-height: 0" in styles.text

    shared_script = client.get("/debug-assets/ui-core.js")
    shared_styles = client.get("/debug-assets/components.css")
    katex_script = client.get("/debug-assets/vendor/katex/katex.min.js")
    katex_styles = client.get("/debug-assets/vendor/katex/katex.min.css")
    assert "function renderLatex" in shared_script.text
    assert "appendRichInline" in shared_script.text
    assert "window.katex.render" in shared_script.text
    assert 'trust: false' in shared_script.text
    assert "math-latex-fallback" in shared_script.text
    assert ".math-display" in shared_styles.text
    assert ".katex-display" in shared_styles.text
    assert katex_script.status_code == 200
    assert katex_styles.status_code == 200
    assert "/debug-assets/vendor/katex/katex.min.js" in page.text


def test_workspace_capabilities_hide_provider_implementation(client) -> None:
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    features = response.json()["workspace_features"]
    assert {item["id"] for item in features} == {
        "course_qa",
        "academic_problem_solving",
        "lesson_prep",
        "assignment_review",
        "academic_writing",
        "data_analysis",
    }
    assert all("provider" not in item and "flow_id" not in item for item in features)


def test_debug_agent_console_page_and_production_controls(client) -> None:
    page = client.get("/debug/agents")
    script = client.get("/debug-assets/agents.js")

    assert page.status_code == 200
    assert "Agent 管理" in page.text
    assert "运行 Mock" in page.text
    assert "Dry Run" in page.text
    assert "完整 Flow ID" in page.text
    assert "XINGCHEN_" not in page.text
    assert "/api/v1/debug/agents/" in script.text


def test_student_image_upload_normalizes_and_rejects_wrong_type(client) -> None:
    valid = client.post(
        "/api/v1/files",
        data={"purpose": "student_solver_image"},
        files={"upload": ("circuit.png", png_bytes(), "image/png")},
    )
    invalid = client.post(
        "/api/v1/files",
        data={"purpose": "student_solver_image"},
        files={"upload": ("notes.pdf", b"%PDF-test", "application/pdf")},
    )

    assert valid.status_code == 201, valid.text
    assert valid.json()["content_type"] == "image/png"
    assert not valid.json()["storage_key"].startswith("C:")
    assert invalid.status_code == 422


def test_student_followup_receives_short_session_context(api, client) -> None:
    session = api.create_session()
    first = api.create_task(session["id"])
    assert api.wait_for_task(first["id"])["status"] == "completed"

    second = api.create_task(session["id"])
    second_task = client.get(f"/api/v1/tasks/{second['id']}").json()
    options = second_task["input_content"]["options"]

    assert options["previous_agent"] == "ACADEMIC_PROBLEM_SOLVER"
    assert options["previous_answer_summary"]
    assert len(options["previous_answer_summary"]) <= 600
    assert len(options["conversation_summary"]) <= 800


def test_course_switch_clears_previous_answer_context(settings) -> None:
    session = SessionModel(
        id="session-context",
        user_id="student",
        course_id="CT",
        context_data={
            "active_course": "CT",
            "previous_answer_summary": "上一门课程回答",
            "conversation_summary": "上一门课程对话",
            "last_evidence_ids": ["S1"],
        },
    )
    request = AgentRequest(
        session_id=session.id,
        user_id="student",
        course_id="AE",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "负反馈是什么？"},
    )

    updated = SessionContextService(settings).apply(session, request)

    assert updated.options["course_context_reset"] is True
    assert updated.options["previous_answer_summary"] == ""
    assert updated.options["conversation_summary"] == ""
    assert updated.options["last_evidence_ids"] == []


def test_student_single_image_task_uses_existing_attachment_contract(
    api, client
) -> None:
    session = api.create_session()
    upload = client.post(
        "/api/v1/files",
        data={"purpose": "student_solver_image"},
        files={"upload": ("circuit.png", png_bytes(), "image/png")},
    )
    file = upload.json()
    attachment = {
        key: file[key]
        for key in (
            "id",
            "filename",
            "content_type",
            "size_bytes",
            "storage_key",
            "checksum_sha256",
        )
    }
    attachment["file_id"] = attachment.pop("id")

    task = api.create_task(session["id"], attachments=[attachment])
    final = api.wait_for_task(task["id"])

    assert final["status"] == "completed"
    assert final["agent_id"] == "ACADEMIC_PROBLEM_SOLVER"
