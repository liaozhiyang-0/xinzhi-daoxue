from __future__ import annotations

import io
from pathlib import Path

from app.contracts import AgentRequest, Intent
from app.models import SessionModel
from app.services.session_context import SessionContextService
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (24, 16), "white").save(output, format="PNG")
    return output.getvalue()


def test_browser_acceptance_uses_an_isolated_test_database() -> None:
    script = (ROOT / "scripts" / "run_web_ui_browser_acceptance.js").read_text(
        encoding="utf-8"
    )

    assert "TEST_DATABASE_URL: testDatabaseURL" in script
    assert "xinzhi-browser-acceptance-${process.pid}.db" in script


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
    assert 'id="image-input" type="file" multiple' in page.text
    assert "async function uploadMaterials()" in script.text
    assert "let pendingMaterialFiles = []" in script.text
    assert "function appendMaterialFiles(files)" in script.text
    assert 'id="preview-images"' in page.text
    assert "20260730-image-runtime-v7" in page.text
    assert "ui-core.js?v=20260801-auth-entry-v1" in page.text
    assert 'id="left-resizer"' in page.text
    assert 'id="right-resizer"' in page.text
    assert 'id="document-dialog"' in page.text
    assert 'id="document-dialog-match"' in page.text
    assert 'id="document-page-previous"' in page.text
    assert 'id="document-page-next"' in page.text
    assert "function openEvidenceDocument(item)" in script.text
    assert "function loadEvidenceDocumentPage(item, offset = null)" in script.text
    assert "documentPageState.controller?.abort()" in script.text
    assert "rewriteKnowledgeDocumentImages" in script.text
    assert "relatedImageCard" in script.text
    assert "academic_generation_direct_model" in script.text
    assert "message-image-gallery" in script.text
    assert "appendStoredAttachmentImages" in script.text
    assert "/content?user_id=" in script.text
    assert "initializeResizablePanels()" in script.text
    assert "materials.map((item) => attachmentRef(item.uploaded))" in script.text
    assert "let pendingLearningFollowUp = null" in script.text
    assert 'intent: requestedIntent' in script.text
    assert "source_task_id: learningFollowUp?.source_task_id" in script.text
    assert "pendingLearningFollowUp = result.follow_up_context || null" in script.text
    assert 'id="teaching-mode"' in page.text
    assert 'value="direct_answer"' in page.text
    assert 'value="guided_learning"' in page.text
    assert 'value="check_my_work"' in page.text
    assert 'id="student-attempt-input"' in page.text
    assert 'id="teaching-loop-panel"' in page.text
    assert 'id="submit-teaching-response"' in page.text
    assert 'id="request-more-hint"' in page.text
    assert 'id="switch-direct-answer"' in page.text
    assert "teaching_mode: teachingMode" in script.text
    assert (
        'student_attempt: teachingMode === "check_my_work" '
        "? { raw_text: studentAttempt } : undefined"
    ) in script.text
    assert "function renderTeachingLoop(structured)" in script.text
    assert "function usesInteractiveTeaching(structured = {})" in script.text
    assert (
        "if (!loop || !usesInteractiveTeaching(structured))" in script.text
    )
    assert (
        '["guided_learning", "check_my_work"].includes(mode)' in script.text
    )
    assert (
        "retests.filter((item) => item.source_task_id === task.id)"
        in script.text
    )
    assert "function verificationPresentation(report)" in script.text
    assert 'data-context-tab="context"' in page.text
    assert 'id="context-usage"' in page.text
    assert "function renderContextUsage(result = {})" in script.text
    assert "presentation.answer_quality_message" in script.text
    assert '"答案质量"' in script.text
    assert "active_memory_ids" in script.text
    assert "本次已使用" in script.text
    assert "从模型摘要中自动保存明确的稳定偏好" in page.text
    assert "ownedTaskUrl(state.currentTask.id)" in script.text
    assert 'audience: "student"' in script.text
    assert 'api("/api/v1/capabilities")' in script.text
    assert "/api/v1/sessions/${state.sessionId}/tasks?limit=50" in script.text
    assert "archiveCurrentAnswer()" in script.text
    assert "scrollbar-gutter: stable" in styles.text
    assert ".workspace-center" in styles.text and "min-height: 0" in styles.text
    assert ".related-image-gallery button" in styles.text
    assert "aspect-ratio: 4 / 3" in styles.text
    assert ".evidence-card" in styles.text and "overflow: hidden" in styles.text

    shared_script = client.get("/debug-assets/ui-core.js")
    shared_styles = client.get("/debug-assets/components.css")
    katex_script = client.get("/debug-assets/vendor/katex/katex.min.js")
    katex_styles = client.get("/debug-assets/vendor/katex/katex.min.css")
    assert "function renderLatex" in shared_script.text
    assert "appendRichInline" in shared_script.text
    assert 'text.startsWith("\\\\[", index)' in shared_script.text
    assert 'text.startsWith("$$", index)' in shared_script.text
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
    content = client.get(
        f"/api/v1/files/{file['id']}/content",
        params={"user_id": "user-test"},
    )
    forbidden = client.get(
        f"/api/v1/files/{file['id']}/content",
        params={"user_id": "another-user"},
    )

    assert final["status"] == "completed"
    assert final["agent_id"] == "ACADEMIC_PROBLEM_SOLVER"
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.content.startswith(b"\x89PNG")
    assert forbidden.status_code == 404


def test_student_multi_image_task_reaches_existing_task_runner(api, client) -> None:
    session = api.create_session()
    attachments = []
    for index in (1, 2):
        upload = client.post(
            "/api/v1/files",
            data={"purpose": "student_solver_image"},
            files={
                "upload": (
                    f"circuit-{index}.png",
                    png_bytes(),
                    "image/png",
                )
            },
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
        attachments.append(attachment)

    task = api.create_task(session["id"], attachments=attachments)
    final = api.wait_for_task(task["id"])

    assert final["status"] == "completed"
    assert final["agent_id"] == "ACADEMIC_PROBLEM_SOLVER"
    assert len(final["input_content"]["attachments"]) == 2
