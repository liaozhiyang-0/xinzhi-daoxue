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
    alias = client.get("/student", follow_redirects=False)
    page = client.get("/workspace")
    app = (ROOT / "apps/web/src/app/App.tsx").read_text(encoding="utf-8")
    composer = (ROOT / "apps/web/src/features/chat/Composer.tsx").read_text(
        encoding="utf-8"
    )
    transport = (ROOT / "apps/web/src/task-transport.ts").read_text(encoding="utf-8")
    contracts = (ROOT / "apps/web/src/workspace-contracts.ts").read_text(
        encoding="utf-8"
    )
    styles = (ROOT / "apps/web/src/styles/app.css").read_text(encoding="utf-8")

    assert alias.status_code == 307
    assert alias.headers["location"] == "/workspace"
    assert page.status_code == 200
    assert '<div id="root"></div>' in page.text
    assert "/react-assets/assets/index-" in page.text
    assert "legacy-workspace-contract" not in page.text
    assert "createTask" in app
    assert "getTaskRuntimeControls" in app
    assert "WorkspaceContextPane" in app
    assert "new EventSource" in transport
    assert "task.completed" in transport
    assert "prefer_internal_agents: true" in contracts
    assert "buildStudentTaskPayload" in contracts
    assert "responseDepth" in composer
    assert "composer-resize-handle" in composer
    assert "workspace-resizer" in styles
    assert "overflow-y: auto" in styles
    for path in ("workspace.html", "workspace.js", "student.html", "student.js"):
        assert client.get(f"/debug-assets/{path}").status_code == 404


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
