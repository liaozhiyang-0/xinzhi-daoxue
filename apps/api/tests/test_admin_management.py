from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from app.core.config import Settings
from app.main import create_app
from app.models import AccountModel
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    async def update_role() -> None:
        async with client.app.state.session_factory() as db:
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
