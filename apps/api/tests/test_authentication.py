from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


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


def register(client: TestClient, login: str = "student@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "login": login,
            "password": "correct horse battery staple",
            "display_name": "测试学生",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_me_refresh_and_logout(auth_client: TestClient) -> None:
    registered = register(auth_client)
    assert registered["account"]["login"] == "student@example.com"
    assert "access_token" not in registered

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == registered["account"]["id"]

    refreshed = auth_client.post("/api/v1/auth/refresh", json={})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["account"]["id"] == registered["account"]["id"]

    logged_out = auth_client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 204
    assert auth_client.get("/api/v1/auth/me").status_code == 401


def test_auth_required_rejects_anonymous_and_uses_authenticated_owner(
    auth_client: TestClient,
) -> None:
    auth_client.cookies.clear()
    response = auth_client.post(
        "/api/v1/sessions",
        json={"user_id": "attacker", "course_id": "CT", "title": "匿名"},
    )
    assert response.status_code == 401

    registered = register(auth_client)
    account_id = registered["account"]["id"]
    created = auth_client.post(
        "/api/v1/sessions",
        json={"user_id": "attacker", "course_id": "CT", "title": "可信身份"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["user_id"] == account_id

    listed = auth_client.get(
        "/api/v1/sessions", params={"user_id": "attacker"}
    )
    assert listed.status_code == 200
    assert [item["user_id"] for item in listed.json()] == [account_id]


def test_guest_mode_creates_isolated_identity_and_logout_clears_it(
    auth_client: TestClient,
) -> None:
    auth_client.cookies.clear()
    issued = auth_client.post("/api/v1/auth/guest")
    assert issued.status_code == 200, issued.text
    guest_id = issued.json()["user_id"]
    assert guest_id.startswith("guest_")
    assert issued.json()["guest"] is True

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == guest_id

    created = auth_client.post(
        "/api/v1/sessions",
        json={"user_id": "attacker", "course_id": "CT", "title": "游客会话"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["user_id"] == guest_id

    assert auth_client.post("/api/v1/auth/logout").status_code == 204
    assert auth_client.get("/api/v1/auth/me").status_code == 401


def test_login_rate_limit_is_keyed_by_login_and_ip(
    auth_client: TestClient,
) -> None:
    register(auth_client)
    auth_client.post("/api/v1/auth/logout")
    for _ in range(5):
        failed = auth_client.post(
            "/api/v1/auth/login",
            json={"login": "student@example.com", "password": "wrong password"},
        )
        assert failed.status_code == 401
    limited = auth_client.post(
        "/api/v1/auth/login",
        json={"login": "student@example.com", "password": "wrong password"},
    )
    assert limited.status_code == 429


def test_debug_surfaces_require_admin_when_auth_is_required(
    auth_client: TestClient,
) -> None:
    auth_client.cookies.clear()
    assert auth_client.get("/api/v1/debug/rag/status").status_code == 401

    register(auth_client, login="student-debug@example.com")
    assert auth_client.get("/api/v1/debug/rag/status").status_code == 403
