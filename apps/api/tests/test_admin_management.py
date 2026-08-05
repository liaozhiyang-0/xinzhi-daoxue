from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from app.core.config import Settings
from app.main import create_app
from app.models import AccountModel, FileModel, SessionModel, TaskModel, TaskStatus
from app.services.evaluation_attachment_maintenance import (
    cleanup_stale_evaluation_attachments,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from .test_authentication import register


@pytest.fixture
def auth_client(settings: Settings) -> Iterator[TestClient]:
    auth_settings = settings.model_copy(
        update={
            "auth_required": True,
            "auth_allow_registration": True,
            "auth_scrypt_n_log2": 14,
        }
    )
    app: FastAPI = create_app(auth_settings)
    with TestClient(app) as client:
        yield client


def promote_to_admin(client: TestClient, account_id: str) -> None:
    app = cast(FastAPI, client.app)

    async def update_role() -> None:
        async with app.state.session_factory() as db:
            account = await db.get(AccountModel, account_id)
            assert account is not None
            account.role = "admin"
            await db.commit()

    asyncio.run(update_role())


def test_admin_can_manage_accounts_sessions_and_audit_log(
    auth_client: TestClient,
) -> None:
    admin = register(auth_client, login="root@example.com")
    promote_to_admin(auth_client, admin["account"]["id"])

    overview = auth_client.get("/api/v1/admin/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["account_count"] == 1
    assert overview.json()["audit_event_count"] >= 1

    created = auth_client.post(
        "/api/v1/admin/accounts",
        json={
            "login": "teacher@example.com",
            "password": "teacher password secure",
            "display_name": "Teacher",
            "role": "teacher",
        },
    )
    assert created.status_code == 201, created.text
    teacher_id = created.json()["id"]

    listed = auth_client.get("/api/v1/admin/accounts", params={"role": "teacher"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == teacher_id

    disabled = auth_client.patch(
        f"/api/v1/admin/accounts/{teacher_id}",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    reset = auth_client.post(
        f"/api/v1/admin/accounts/{teacher_id}/reset-password",
        json={"password": "new teacher password"},
    )
    assert reset.status_code == 200
    assert reset.json()["status"] == "active"

    demote_self = auth_client.patch(
        f"/api/v1/admin/accounts/{admin['account']['id']}",
        json={"role": "student"},
    )
    assert demote_self.status_code == 409

    sessions = auth_client.get("/api/v1/admin/sessions")
    assert sessions.status_code == 200
    assert sessions.json()

    audit = auth_client.get("/api/v1/admin/audit-logs")
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()}
    assert "admin.account.create" in actions
    assert "admin.account.update" in actions
    assert "admin.account.reset_password" in actions


def test_admin_api_rejects_student(auth_client: TestClient) -> None:
    register(auth_client, login="student-admin@example.com")
    response = auth_client.get("/api/v1/admin/overview")
    assert response.status_code == 403


def test_admin_can_toggle_feedback_loop(auth_client: TestClient) -> None:
    admin = register(auth_client, login="feature-admin@example.com")
    promote_to_admin(auth_client, admin["account"]["id"])

    listed = auth_client.get("/api/v1/admin/settings/features")
    assert listed.status_code == 200
    assert listed.json()[0]["key"] == "feedback_loop"
    assert listed.json()[0]["enabled"] is True

    updated = auth_client.patch(
        "/api/v1/admin/settings/features/feedback_loop",
        json={"enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert auth_client.get("/api/v1/feedback/status").json()["enabled"] is False

    audit = auth_client.get("/api/v1/admin/audit-logs").json()
    assert any(item["action"] == "admin.feature.toggle" for item in audit)


def test_admin_can_inspect_ingested_files(auth_client: TestClient) -> None:
    admin = register(auth_client, login="file-admin@example.com")
    promote_to_admin(auth_client, admin["account"]["id"])

    uploaded = auth_client.post(
        "/api/v1/files",
        files={"upload": ("admin-note.txt", b"admin material", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text

    summary = auth_client.get("/api/v1/admin/file-summary")
    assert summary.status_code == 200
    assert summary.json()["ready"] >= 1

    files = auth_client.get(
        "/api/v1/admin/files", params={"ingestion_status": "ready"}
    )
    assert files.status_code == 200
    assert files.json()["total"] >= 1
    assert files.json()["items"][0]["extracted_text"] == "admin material"


def test_admin_can_inspect_evaluation_attachment_residue(
    auth_client: TestClient,
) -> None:
    admin = register(auth_client, login="residue-admin@example.com")
    promote_to_admin(auth_client, admin["account"]["id"])
    now = datetime.now(UTC)
    old = now - timedelta(days=2)
    recent = now - timedelta(hours=1)
    app = cast(FastAPI, auth_client.app)

    async def seed() -> None:
        async with app.state.session_factory() as db:
            session = SessionModel(
                id="session-eval-residue",
                user_id=admin["account"]["id"],
                course_id="CT",
                title="residue test",
            )
            active_task = TaskModel(
                id="task-eval-active",
                session_id=session.id,
                user_id=admin["account"]["id"],
                course_id="CT",
                intent="evaluation",
                agent_id="mock-agent",
                status=TaskStatus.RUNNING,
                input_content={},
                created_at=old,
                started_at=old + timedelta(minutes=1),
            )
            terminal_task = TaskModel(
                id="task-eval-terminal",
                session_id=session.id,
                user_id=admin["account"]["id"],
                course_id="CT",
                intent="evaluation",
                agent_id="mock-agent",
                status=TaskStatus.COMPLETED,
                input_content={},
                created_at=old,
                started_at=old + timedelta(minutes=2),
                completed_at=old + timedelta(minutes=5),
            )
            failed_task = TaskModel(
                id="task-eval-failed",
                session_id=session.id,
                user_id=admin["account"]["id"],
                course_id="CT",
                intent="evaluation",
                agent_id="mock-agent",
                status=TaskStatus.FAILED,
                route_status="fallback",
                failure_category="provider_timeout",
                cancellation_requested=True,
                input_content={},
                created_at=old,
                started_at=old + timedelta(minutes=3),
                completed_at=old + timedelta(minutes=6),
            )
            db.add_all(
                [
                    session,
                    active_task,
                    terminal_task,
                    failed_task,
                    FileModel(
                        id="file-eval-unbound-old",
                        owner_user_id=admin["account"]["id"],
                        filename="old-unbound.png",
                        content_type="image/png",
                        size_bytes=3,
                        storage_key="local:eval/old-unbound.png",
                        checksum_sha256="a" * 64,
                        purpose="evaluation_attachment",
                        created_at=old,
                    ),
                    FileModel(
                        id="file-eval-unbound-recent",
                        owner_user_id=admin["account"]["id"],
                        filename="recent-unbound.png",
                        content_type="image/png",
                        size_bytes=5,
                        storage_key="local:eval/recent-unbound.png",
                        checksum_sha256="b" * 64,
                        purpose="evaluation_attachment",
                        created_at=recent,
                    ),
                    FileModel(
                        id="file-eval-active-old",
                        owner_user_id=admin["account"]["id"],
                        task_id=active_task.id,
                        filename="active.png",
                        content_type="image/png",
                        size_bytes=7,
                        storage_key="local:eval/active.png",
                        checksum_sha256="c" * 64,
                        purpose="evaluation_attachment",
                        created_at=old,
                    ),
                    FileModel(
                        id="file-eval-terminal-old",
                        owner_user_id=admin["account"]["id"],
                        task_id=terminal_task.id,
                        filename="terminal.png",
                        content_type="image/png",
                        size_bytes=11,
                        storage_key="local:eval/terminal.png",
                        checksum_sha256="d" * 64,
                        purpose="evaluation_attachment",
                        created_at=old,
                    ),
                ]
            )
            await db.commit()

    asyncio.run(seed())
    response = auth_client.get("/api/v1/admin/evaluation-attachment-residue")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["purpose"] == "evaluation_attachment"
    assert payload["total_file_count"] == 4
    assert payload["total_bytes"] == 26
    assert payload["unbound_file_count"] == 2
    assert payload["active_task_file_count"] == 1
    assert payload["terminal_task_file_count"] == 1
    assert payload["missing_task_file_count"] == 0
    assert payload["cleanup_candidate_count"] == 2
    assert payload["cleanup_candidate_bytes"] == 14

    summary = auth_client.get("/api/v1/admin/task-summary")
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload["failure_category_counts"] == {
        "provider_timeout": 1
    }
    assert summary_payload["provider_counts"] == {"mock": 3}
    assert summary_payload["route_status_counts"] == {"fallback": 1, "selected": 2}
    assert summary_payload["cancellation_requested_count"] == 1

    observability = auth_client.get(
        "/api/v1/admin/task-observability", params={"row_limit": 10}
    )
    assert observability.status_code == 200, observability.text
    observability_payload = observability.json()
    assert observability_payload["task_count"] == 3
    assert observability_payload["truncated"] is False
    assert observability_payload["measured_total_latency_count"] == 2
    assert observability_payload["average_total_latency_ms"] == 180000.0
    assert observability_payload["p50_total_latency_ms"] == 180000.0
    assert observability_payload["p95_total_latency_ms"] == 180000.0
    assert observability_payload["measured_queue_latency_count"] == 3
    assert observability_payload["average_queue_latency_ms"] == 120000.0
    assert observability_payload["p95_queue_latency_ms"] == 180000.0
    assert observability_payload["data_quality_warnings"] == []

    invalid_window = auth_client.get(
        "/api/v1/admin/task-observability",
        params={
            "window_start": (now + timedelta(minutes=1)).isoformat(),
            "window_end": now.isoformat(),
        },
    )
    assert invalid_window.status_code == 422

    async def cleanup_candidates() -> tuple[int, list[str]]:
        async with app.state.session_factory() as db:
            removed = await cleanup_stale_evaluation_attachments(
                db, app.state.settings, limit=10
            )
            await db.commit()
            remaining = list(
                await db.scalars(
                    select(FileModel.id).where(
                        FileModel.purpose == "evaluation_attachment"
                    )
                )
            )
            return removed, remaining

    removed, remaining = asyncio.run(cleanup_candidates())
    assert removed == 2
    assert set(remaining) == {"file-eval-unbound-recent", "file-eval-active-old"}
