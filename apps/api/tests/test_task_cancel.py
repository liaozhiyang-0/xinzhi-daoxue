from io import BytesIO

from PIL import Image


def test_queued_task_can_be_cancelled(api, client, monkeypatch) -> None:
    monkeypatch.setattr(client.app.state.task_runner, "submit", lambda task_id: True)
    session = api.create_session()
    task = api.create_task(session["id"])
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_queued_evaluation_task_cleans_attachment_on_cancel(
    api, client, settings, monkeypatch
) -> None:
    monkeypatch.setattr(client.app.state.task_runner, "submit", lambda task_id: True)
    image_data = BytesIO()
    with Image.new("RGB", (2, 2), color="white") as image:
        image.save(image_data, format="PNG")
    uploaded = client.post(
        "/api/v1/files",
        files={"upload": ("diagram.png", image_data.getvalue(), "image/png")},
        data={"purpose": "evaluation_attachment"},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()
    session = api.create_session()
    task = api.create_task(
        session["id"],
        attachments=[
            {
                key: attachment[key]
                for key in (
                    "id",
                    "filename",
                    "content_type",
                    "size_bytes",
                    "storage_key",
                    "checksum_sha256",
                    "ingestion_status",
                    "page_count",
                    "extracted_text",
                    "extraction_metadata",
                )
                if key != "id"
            }
            | {"file_id": attachment["id"]}
        ],
    )
    cancelled = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/files/{attachment['id']}").status_code == 404
    storage_key = str(attachment["storage_key"])
    if storage_key.startswith("local:"):
        assert not (
            settings.local_storage_path / storage_key.removeprefix("local:")
        ).exists()


def test_running_mock_task_can_be_cancelled(api, client) -> None:
    session = api.create_session()
    task = api.create_task(
        session["id"],
        options={
            "mock_delay_seconds": 1.0,
            "debug_agent_id": "SOLVER_CT_V1",
        },
        user_role="admin",
    )
    api.wait_for_task(task["id"], statuses={"running"})
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["cancellation_requested"] is True
    assert api.wait_for_task(task["id"])["status"] == "cancelled"


def test_completed_task_cannot_be_cancelled(api, client) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 409
