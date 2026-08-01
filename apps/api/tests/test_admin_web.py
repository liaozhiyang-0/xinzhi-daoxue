from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_and_login_pages_are_available(client: TestClient) -> None:
    admin = client.get("/admin")
    assert admin.status_code == 200
    assert "/debug-assets/admin.css" in admin.text
    assert "/debug-assets/admin.js" in admin.text

    login = client.get("/login?next=/admin")
    assert login.status_code == 200
    assert "/debug-assets/login.js" in login.text
    assert "登录账号" in login.text


def test_admin_api_is_not_open_to_anonymous_users(client: TestClient) -> None:
    response = client.get("/api/v1/admin/overview")
    assert response.status_code == 401
