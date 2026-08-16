from __future__ import annotations

import io
from pathlib import Path

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
    materials = client.get("/debug-assets/workspace-materials.js")
    transport = client.get("/debug-assets/workspace-task-transport.js")
    materials_ts = client.get("/debug-assets/ts/materials.js")
    transport_ts = client.get("/debug-assets/ts/task-transport.js")
    contracts = client.get("/debug-assets/ts/workspace-contracts.js")
    styles = client.get("/debug-assets/workspace-v2.css")
    script_text = "\n".join(
        (
            script.text,
            materials.text,
            transport.text,
            materials_ts.text,
            transport_ts.text,
            contracts.text,
        )
    )

    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store, max-age=0"
    assert "id=\"mode-control\"" not in page.text
    for capability in (
        "lesson_prep",
        "assignment_review",
        "student_learning_path",
        "academic_search",
        "knowledge_governance",
        "solve_problem",
    ):
        assert f'data-capability="{capability}"' in page.text
    assert page.text.count("data-capability=") == 6
    assert "data-capability=\"course_qa\"" not in page.text
    assert "data-capability=\"academic_problem_solving\"" not in page.text
    assert "data-capability=\"data_analysis\"" not in page.text
    assert 'class="composer-agent-track"' not in page.text
    assert 'id="detected-course"' in page.text
    assert 'id="detected-learning-mode"' in page.text
    assert '<select id="course-select"' not in page.text
    assert '<select id="teaching-mode"' not in page.text
    assert 'id="image-input" type="file" multiple' in page.text
    assert 'type="module"' in page.text
    assert "api(\"/api/v1/tasks\"" in script_text
    assert "new EventSource" in script_text
    assert "task.error_message" in script_text
    assert "prefer_internal_agents: true" in script_text
    assert "allow_cloud" not in script_text
    assert "createMaterialManager" in script_text
    assert "createTaskTransport" in script_text
    assert "./ts/workspace-contracts.js" in script.text
    assert "buildStudentTaskPayload" in contracts.text
    assert "id=\"preview-images\"" in page.text
    assert "20260815-subject-agents-v1" in page.text
    assert "function openEvidenceDocument(item)" in script.text
    assert "function loadEvidenceDocumentPage(item, offset = null)" in script.text
    assert "documentPageState.controller?.abort()" in script.text
    assert "initializeResizablePanels()" in script.text
    assert "businessSectionAlreadyInAnswer" in script.text
    assert "function messageStatusText(status)" in script.text
    assert "historyRequestSequence" in script.text
    assert "renderedAssistantTaskIds" in script.text
    assert "state.activeTaskWait" in script_text
    assert "runSequence !== state.runSequence" in script.text
    assert (
        "attachments: materials.map((item) => attachmentRef(item.uploaded))"
        in contracts.text
    )
    assert "let pendingLearningFollowUp = null" in script.text
    assert "intent: requestedIntent" in script.text
    assert "source_task_id: learningFollowUp?.source_task_id" in contracts.text
    assert "workspace-answer" in styles.text
    assert ".workspace-composer > #question-input" in styles.text
    assert "scrollbar-width: thin" in styles.text

def test_student_multi_image_task_reaches_runtime(api, client) -> None:
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
