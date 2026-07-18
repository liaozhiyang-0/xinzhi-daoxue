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
    script = client.get("/debug-assets/student.js")

    assert page.status_code == 200
    assert "知识问答" in page.text
    assert "电路解题" in page.text
    assert "今天想学习什么" in page.text
    assert "Mock形式" not in page.text
    assert "Qdrant" not in page.text
    assert "Flow ID" not in page.text
    assert "Xingchen" not in page.text
    assert 'api("/api/v1/tasks"' in script.text
    assert "/debug/rag/run" not in script.text
    assert "xingchen-api" not in script.text
    assert "new EventSource" in script.text
    assert "该课程完整解题工作流尚未开放" in script.text


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

    assert options["previous_agent"] == "SOLVER_CT_V1"
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
    assert final["agent_id"] == "SOLVER_CT_V1"
