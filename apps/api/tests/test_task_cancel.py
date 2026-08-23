from io import BytesIO
from unittest.mock import AsyncMock

from PIL import Image


def test_queued_task_can_be_cancelled(api, client, monkeypatch) -> None:
    monkeypatch.setattr(
        client.app.state.task_executor, "submit", AsyncMock(return_value=True)
    )
    session = api.create_session()
    task = api.create_task(session["id"])
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["failure_category"] == "cancelled"
    assert response.json()["error_message"] == "任务已取消"
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    terminal_data = events[-1]["event_data"]["data"]
    assert terminal_data["terminal_status"] == "cancelled"
    assert terminal_data["failure_category"] == "cancelled"
    assert terminal_data["error_code"] == "cancelled"
    assert terminal_data["error_message"] == "任务已取消"


def test_queued_cancel_persists_when_provider_cancel_fails(
    api, client, monkeypatch
) -> None:
    monkeypatch.setattr(
        client.app.state.task_executor, "submit", AsyncMock(return_value=True)
    )

    async def fail_provider_cancel(_run_id: str) -> None:
        raise RuntimeError("provider cancel unavailable")

    monkeypatch.setattr(client.app.state.provider, "cancel", fail_provider_cancel)
    session = api.create_session()
    task = api.create_task(session["id"])

    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["failure_category"] == "cancelled"


def test_queued_evaluation_task_cleans_attachment_on_cancel(
    api, client, settings, monkeypatch
) -> None:
    monkeypatch.setattr(
        client.app.state.task_executor, "submit", AsyncMock(return_value=True)
    )
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
